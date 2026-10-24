# Evidencia

Todo lo que hay en esta carpeta salió de una ejecución real en AWS, región `us-east-1`. El
stack se creó con un solo `terraform apply`, se verificó de extremo a extremo y se eliminó
después. Nada de esto es simulado.

| Archivo | Qué demuestra |
| --- | --- |
| `requests.json` | Las dos peticiones reales al endpoint, con cabeceras y cuerpos |
| `s3-object.json` | El objeto persistido en S3, con tamaño y fecha |
| `s3-ls.txt` | Salida de `aws s3 ls --recursive` sobre el prefijo de resultados |
| `security-and-network-checks.json` | Bloqueo público, versionado, cifrado, topología, throttling y cifrado de Redis |
| `deployment-lifecycle.json` | Recursos creados y eliminados por Terraform, y resultado end-to-end |
| `cleanup-checks.json` | Comprobación independiente de que no queda ningún recurso en AWS |
| `unit-tests.txt` | Salida de pytest (pruebas con dobles, distintas de las de AWS) |
| `01-vpc-resource-map.png` | Mapa de recursos de la VPC en la consola de AWS |
| `02-s3-results.png` | Bucket de S3 con el objeto guardado |
| `03-elasticache.png` | Caché Redis OSS en la consola de ElastiCache |
| `04-lambda-vpc.png` | Lambda con su disparador de API Gateway y su configuración de VPC |

## El flujo verificado

La primera petición devuelve `X-Cache: MISS` porque la clave no está en Redis: el handler
persiste el resultado en S3 y lo cachea durante 60 segundos. La segunda, con el mismo
cuerpo, devuelve `X-Cache: HIT` y exactamente la misma respuesta. El objeto resultante
aparece en S3 con 409 bytes.

```json
{
  "status": 200,
  "headers": { "X-Cache": "MISS" },
  "response_body": {
    "id": "441426a050598727ff11a4aeb76572f3ac906cd562563d4432bf57ca0eca2f28",
    "object_key": "results/2026-10-24/441426a050598727ff11a4aeb76572f3ac906cd562563d4432bf57ca0eca2f28.json"
  }
}
```

## Datos ocultos en las capturas

Antes de publicarlas se ocultaron los datos de identidad, sin tocar ningún valor técnico
de la configuración que se muestra:

- La barra de pestañas y la barra de direcciones del navegador, con pestañas personales y
  el correo.
- El menú de usuario de la consola: nombre de usuario, alias e **ID de cuenta AWS**.
- El campo *Owner ID* del panel de detalles de la VPC.
- El ARN de la función Lambda, que incluye el ID de cuenta.

Los identificadores de recursos (VPC, subnets, security groups, bucket, endpoint) se
dejaron visibles a propósito: son la evidencia de la topología y no son credenciales. No
se capturaron las variables de entorno de Lambda ni el token de autenticación de Redis,
que nunca aparecen en estas vistas. Cada imagen se revisó después de procesarla para
confirmar que no quedara nada legible.

## Sobre los tiempos

El registro de peticiones usa el reloj del equipo. Las cabeceras `Date`, el campo
`processed_at` y `LastModified` provienen de AWS, así que puede haber un pequeño desfase.
El listado de `aws s3 ls` muestra la hora local.
