# Pruebas manuales

En una instalación de prueba, comprueba que el puerto local responde en `/health`. Abre el origen HTTPS desde el navegador y el móvil, entra con una cuenta de prueba y revisa Inicio y Biblioteca. Al estrenar una instalación, comprueba la biblioteca vacía antes de importar datos.

Para probar reproducción sin material personal, genera el audio sintético y monta el overlay del laboratorio en una instancia aparte. Verifica la reproducción completa y la búsqueda dentro de la pista. Si pruebas dos cuentas, comprueba que cada una ve sus listas y su historial. [Preparación de los fixtures](../README.md#audio-y-metadatos-de-prueba)

Las comprobaciones del backend y las instrucciones para un ensayo de restauración están en la [guía de integración](../tests/integration/README.md).
