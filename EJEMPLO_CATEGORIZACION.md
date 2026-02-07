# Guia de Categorizacion de Viajes - REGLAS CORRECTAS

**IMPORTANTE:** Estas reglas deben seguirse estrictamente para no perder reembolsos.

---

## REGLA PRINCIPAL: Cuando es LABURO?

**Un viaje es LABURO si involucra CUALQUIERA de las direcciones de trabajo configuradas en `config/settings.json`.**

### REGLA CRITICA: Casa <-> Trabajo = LABURO

**TODOS estos casos son Laburo:**
- Casa -> Oficina
- Oficina -> Casa
- Casa -> Cliente
- Cliente -> Casa
- Cliente A -> Cliente B
- Oficina -> Cliente

**NO importa que el otro extremo sea tu casa. Si involucra una direccion de trabajo, es LABURO.**

---

## Cuando es Personal?

Un viaje es **Personal** si:

1. **NO involucra ninguna direccion de trabajo** configurada
2. **Y** al menos uno de estos:
   - Involucra tu casa y el destino no es laboral
   - Es un viaje entre direcciones personales
   - Es fin de semana/feriado a lugares no laborales

---

## Ejemplos Genericos

### LABURO - Casos Tipicos

| Origen | Destino | Razon |
|--------|---------|-------|
| Casa | Oficina principal | Involucra direccion de trabajo |
| Cliente | Casa | Involucra direccion de trabajo |
| Oficina | Cliente | Ambos son trabajo |
| Casa | Cliente | Involucra direccion de trabajo |

### PERSONAL - Casos Tipicos

| Origen | Destino | Razon |
|--------|---------|-------|
| Casa | Restaurante | No involucra trabajo |
| Bar | Casa | No involucra trabajo |
| Casa | Direccion de amigos | Fin de semana, no laboral |

---

## ERRORES COMUNES A EVITAR

### ERROR 1: Marcar Casa -> Cliente como Personal
```
Casa -> Direccion de trabajo = INCORRECTO si lo marcas Personal
                             = CORRECTO: Es LABURO
```
**Resultado:** Perdes el reembolso de ese viaje.

### ERROR 2: No reconocer todas las direcciones de trabajo
Asegurate de tener TODAS las direcciones de trabajo en `config/settings.json`.

### ERROR 3: Pensar que Casa = Personal
```
Casa -> Oficina = LABURO (no Personal)
Oficina -> Casa = LABURO (no Personal)
```

---

## Como Categorizar Paso a Paso

### Paso 1: Lee origen y destino del viaje

### Paso 2: Contiene ALGUNA direccion de trabajo?

Si **SI** -> **LABURO** (terminar aqui)

Si **NO** -> Continua

### Paso 3: Es fin de semana o feriado?
- Sabado/Domingo -> Probablemente Personal
- Feriados -> Probablemente Personal

### Paso 4: Reconoces la direccion como personal?
- Direcciones conocidas no laborales -> Personal
- Direcciones desconocidas -> Revisar manualmente

---

## Regla de Oro Final

> **"Si hay duda y el viaje involucra CUALQUIER direccion de trabajo -> LABURO"**
>
> **"Solo es Personal si estas 100% seguro que NO involucra trabajo"**

**Es mejor reclamar de mas y que te rechacen, que reclamar de menos y perder dinero.**

---

## Configuracion

Las direcciones se configuran en `config/settings.json`. Ver `config/settings.example.json` para el formato.
