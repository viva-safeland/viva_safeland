# Solución de problemas ZROS (ZROScore)

Cuando intentas ejecutar `uv run zroscore` y obtienes un error como este:

```text
zmq.error.ZMQError: Address already in use (addr='tcp://*:5555')
```

Significa que los puertos `5555` o `5556` (que ZROS usa por defecto para subscritores y publicadores) se quedaron ocupados por un proceso anterior de ZROS o Python que no se cerró correctamente.

## Comandos para liberar los puertos

Puedes usar cualquiera de los siguientes métodos desde la terminal para matar el proceso que está usando los puertos.

### Método 1: Usando `fuser` (Recomendado y más rápido)

Este comando buscará y matará de inmediato el proceso que esté utilizando los puertos tcp 5555 o 5556.

```bash
fuser -k 5555/tcp
fuser -k 5556/tcp
```
*(Si te dice permiso denegado, agrégale `sudo` al inicio: `sudo fuser -k 5555/tcp`)*

### Método 2: Cerrando todos los procesos de ZROSCore y Python

Si el error es causado específicamente porque el broker de ZROS sigue corriendo en el fondo:

```bash
pkill -f zroscore
```

Si tus scripts de `pegasus_bridge.py` o `pegasus_viva.py` se quedaron colgados (zombies), puedes forzar el cierre de todos los procesos de python (esto cerrará todas las simulaciones activas):

```bash
pkill -f python
```

### Método 3: Usando `lsof` para encontrar el PID y luego `kill`

Si quieres ver exactamente qué está ocupando el puerto antes de cerrarlo:

1. Encuentra el ID del proceso (PID):
```bash
lsof -i :5555
```
*(Busca el número en la columna `PID`)*

2. Mata el proceso usando su PID (reemplazando `<PID>` con el número):
```bash
kill -9 <PID>
```
