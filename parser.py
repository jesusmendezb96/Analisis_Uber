#!/usr/bin/env python3
"""
HTML/EML Receipt Parser for Uber and Didi
Extracts: date, origin, destination, amount, currency
"""
import email
from email import policy
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
import re
from decimal import Decimal


def parse_receipt(file_path):
    """
    Parse receipt file (.eml or .html) and extract trip data

    Args:
        file_path: Path to .eml or .html file

    Returns:
        dict with keys: filename, service, date, origin, destination, amount, currency
        Returns None if parsing fails
    """
    file_path = Path(file_path)

    try:
        # Determine file type and get HTML content
        if file_path.suffix.lower() == '.eml':
            html_content, email_msg = _extract_html_from_eml(file_path)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            email_msg = None

        if not html_content:
            return None

        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # Detect service (Uber vs Didi)
        service = _detect_service(file_path, email_msg, soup)

        # Parse based on service
        if service == 'Uber':
            return _parse_uber(file_path, soup, email_msg)
        elif service == 'Didi':
            return _parse_didi(file_path, soup, email_msg)
        else:
            print(f"Unknown service for {file_path.name}")
            return None

    except Exception as e:
        print(f"Error parsing {file_path.name}: {e}")
        return None


def extract_html_from_eml(eml_path):
    """Extract HTML content from .eml file (public API)."""
    return _extract_html_from_eml(eml_path)


def _extract_html_from_eml(eml_path):
    """Extract HTML content from .eml file"""
    with open(eml_path, 'rb') as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    html_content = None
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            html_content = part.get_content()
            break

    if not html_content and msg.get_content_type() == 'text/html':
        html_content = msg.get_content()

    return html_content, msg


def _detect_service(file_path, email_msg, soup):
    """Detect if receipt is from Uber or Didi"""
    # Check filename
    name_lower = file_path.name.lower()
    if 'uber' in name_lower:
        return 'Uber'
    if 'didi' in name_lower or 'precio' in name_lower:
        return 'Didi'

    # Check email From header
    if email_msg and email_msg.get('from'):
        from_header = email_msg['from'].lower()
        if 'uber' in from_header:
            return 'Uber'
        if 'didi' in from_header:
            return 'Didi'

    # Check HTML content
    html_text = soup.get_text().lower()
    if 'uber' in html_text:
        return 'Uber'
    if 'didi' in html_text or 'poné tu precio' in html_text:
        return 'Didi'

    return 'Unknown'


def _parse_uber(file_path, soup, email_msg):
    """Parse Uber receipt HTML"""
    data = {
        'filename': file_path.name,
        'service': 'Uber',
        'date': None,
        'origin': None,
        'destination': None,
        'amount': None,
        'currency': None
    }

    # Extract date from email header
    if email_msg and email_msg.get('date'):
        try:
            # Parse email date
            date_str = email_msg['date']
            # Remove timezone info for simpler parsing
            date_obj = datetime.strptime(date_str.split('+')[0].split('-')[0].strip(), '%a, %d %b %Y %H:%M:%S')
            data['date'] = date_obj.strftime('%Y-%m-%d')
        except:
            pass

    # Also try from payments date if available
    if not data['date']:
        payment_date_elem = soup.find(attrs={'data-testid': 'payments_0_date_time'})
        if payment_date_elem:
            try:
                # Format: "22/01/26 9:06 p.m."
                date_text = payment_date_elem.get_text().strip()
                date_part = date_text.split()[0]  # Get "22/01/26"
                date_obj = datetime.strptime(date_part, '%d/%m/%y')
                data['date'] = date_obj.strftime('%Y-%m-%d')
            except:
                pass

    # Extract amount and currency
    total_elem = soup.find(attrs={'data-testid': 'total_fare_amount'})
    if total_elem:
        amount_text = total_elem.get_text().strip()
        # Format: "ARS 5,938.00" or "ARS�5,938.00"
        match = re.search(r'(ARS|USD|EUR)\s*\$?\s*([\d,]+\.?\d*)', amount_text, re.IGNORECASE)
        if match:
            data['currency'] = match.group(1).upper()
            amount_str = match.group(2).replace(',', '')
            data['amount'] = float(amount_str)

    # Extract addresses
    address_elems = soup.find_all(class_='address-point-desc')
    if len(address_elems) >= 2:
        data['origin'] = address_elems[0].get_text().strip()
        data['destination'] = address_elems[1].get_text().strip()

    return data


def _parse_didi(file_path, soup, email_msg):
    """Parse Didi receipt HTML"""
    data = {
        'filename': file_path.name,
        'service': 'Didi',
        'date': None,
        'origin': None,
        'destination': None,
        'amount': None,
        'currency': 'ARS'  # Didi Argentina always uses ARS
    }

    # Remove script and style tags for cleaner text extraction
    for script in soup(["script", "style"]):
        script.decompose()

    # Get all visible text
    text = soup.get_text()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Extract date - usually at the top (e.g., "vie, 9 ene, 2026")
    for i, line in enumerate(lines[:10]):
        # Look for date pattern
        if re.search(r'\d{4}', line) and any(month in line.lower() for month in ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
            try:
                # Try to parse Spanish date format
                date_match = re.search(r'(\d+)\s+(\w+)[,\s]+(\d{4})', line)
                if date_match:
                    day, month, year = date_match.groups()
                    month_map = {
                        'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                        'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
                        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                    }
                    month_num = month_map.get(month[:3].lower())
                    if month_num:
                        data['date'] = f"{year}-{month_num:02d}-{int(day):02d}"
                        break
            except:
                pass

    # Extract amount - look for "Total" followed by money amount
    for i, line in enumerate(lines):
        if line.lower() == 'total' and i + 1 < len(lines):
            next_line = lines[i + 1]
            # Format: "$20,688.34" or "$ 20,688.34"
            match = re.search(r'\$\s*([\d,]+\.?\d*)', next_line)
            if match:
                amount_str = match.group(1).replace(',', '')
                data['amount'] = float(amount_str)
                break

    # Extract addresses and times
    # Look for time patterns (e.g., "04:14 pm") followed by address
    time_pattern = r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))'
    times_and_indices = []
    for i, line in enumerate(lines):
        if re.search(time_pattern, line):
            times_and_indices.append((i, line))

    # If we found 2+ times, the lines after them should be addresses
    if len(times_and_indices) >= 2:
        # Origin is after first time
        origin_idx = times_and_indices[0][0] + 1
        if origin_idx < len(lines):
            # Take the address (might be split across multiple lines)
            origin_parts = []
            for j in range(origin_idx, min(origin_idx + 3, len(lines))):
                line = lines[j]
                # Stop if we hit another time or number pattern
                if re.search(time_pattern, line) or re.search(r'^\d+[,\.]\d+\s*km', line):
                    break
                origin_parts.append(line)
            data['origin'] = ' '.join(origin_parts).strip()

        # Destination is after second time
        dest_idx = times_and_indices[1][0] + 1
        if dest_idx < len(lines):
            dest_parts = []
            for j in range(dest_idx, min(dest_idx + 3, len(lines))):
                line = lines[j]
                if re.search(time_pattern, line) or re.search(r'^\d+[,\.]\d+\s*km', line) or line.lower() in ['ayuda', 'soporte', 'help']:
                    break
                dest_parts.append(line)
            data['destination'] = ' '.join(dest_parts).strip()

    return data


# Test function
if __name__ == '__main__':
    # Test with sample receipts
    receipts_dir = Path('receipts')

    print("Testing parser...\n")

    for eml_file in receipts_dir.glob('*.eml'):
        print(f"\nParsing: {eml_file.name}")
        result = parse_receipt(eml_file)

        if result:
            print(f"  Service: {result['service']}")
            print(f"  Date: {result['date']}")
            print(f"  Origin: {result['origin'][:60]}..." if result['origin'] and len(result['origin']) > 60 else f"  Origin: {result['origin']}")
            print(f"  Destination: {result['destination'][:60]}..." if result['destination'] and len(result['destination']) > 60 else f"  Destination: {result['destination']}")
            print(f"  Amount: {result['currency']} {result['amount']}")
        else:
            print("  ✗ Failed to parse")
