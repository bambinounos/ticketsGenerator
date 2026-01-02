# Manual de Creación de Imágenes para Boletos y Rifas

Este documento describe las especificaciones recomendadas para las imágenes utilizadas en el sistema de rifas, asegurando que los boletos se generen correctamente y se visualicen de forma adecuada.

## 1. Imagen de Fondo del Boleto (TicketTemplate)

La imagen de fondo es crucial para la apariencia del boleto.

*   **Dimensiones Recomendadas:** 800px (ancho) x 400px (alto).
    *   La relación de aspecto debe ser aproximadamente 2:1.
    *   El sistema ajusta el tamaño, pero mantener esta proporción evita deformaciones.
*   **Formato:** JPG o PNG.
*   **Peso del Archivo:** Se recomienda mantenerlo por debajo de 500KB para asegurar una carga rápida.
*   **Diseño:**
    *   Evite colocar texto importante en los bordes (margen de seguridad de 20px).
    *   Considere que el texto del boleto (nombre, número, cliente) se superpondrá a esta imagen. Use colores claros o zonas con baja opacidad donde vaya a ir el texto para facilitar la lectura.

## 2. Logotipo de la Rifa (Raffle)

*   **Dimensiones:** Cuadrado, mín. 200x200px.
*   **Formato:** PNG con fondo transparente es ideal.
*   **Peso:** Máximo 200KB.

## 3. Imágenes de Productos (Raffle)

*   **Dimensiones:** 800x600px o 800x800px.
*   **Formato:** JPG o PNG.
*   **Peso:** Máximo 1MB.

## 4. Favicon (SiteSettings)

*   **Dimensiones:** 32x32px o 64x64px.
*   **Formato:** ICO o PNG.

## Consideraciones Generales

*   Asegúrese de que las imágenes no infrinjan derechos de autor.
*   Pruebe la generación de un boleto de prueba después de subir una nueva plantilla para verificar que el texto es legible sobre el fondo.
