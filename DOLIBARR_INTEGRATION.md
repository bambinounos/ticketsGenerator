# Integración con Dolibarr 17.04

Este documento detalla cómo configurar la integración entre Dolibarr y el sistema de rifas para generar boletos automáticamente al validar facturas o pedidos.

## Requisitos Previos

1.  Acceso de administrador en Dolibarr.
2.  Acceso de administrador en el sistema de Rifas.

## Configuración en Sistema de Rifas

1.  Ingresa al panel de administración `/admin/`.
2.  Busca la sección **Integración Dolibarr** y haz clic en **Añadir**.
3.  Configura los siguientes campos:
    *   **API Key:** Se genera automáticamente (o puedes definir una propia). *Copia esta clave, la necesitarás en Dolibarr.*
    *   **Rifa Activa:** Selecciona la rifa para la cual se generarán los boletos.
    *   **Boletos por Monto:** Cantidad de boletos a regalar por cada unidad de monto (ej. 1).
    *   **Monto Base ($):** El monto requerido para ganar los boletos (ej. 100.00).
    *   **Integración Activa:** Marca esta casilla para habilitar el sistema.
    *   **Precio del Boleto (Registro):** Precio que se registrará en el boleto generado (usualmente 0.00 si es regalado).

## Configuración en Dolibarr (Trigger)

Para enviar los datos a este sistema, necesitas crear un módulo personalizado o modificar un trigger existente en Dolibarr.

**Archivo a crear/editar:** `htdocs/custom/mimodulo/core/triggers/interface_99_modMimodulo_MyTrigger.class.php`

### Código de Ejemplo (PHP)

```php
<?php

class interface_99_modMimodulo_MyTrigger
{
    public $name = 'MyTrigger';
    public $family = 'mytrigger';
    public $description = 'Trigger para enviar datos a sistema de rifas';
    public $version = '1.0.0';

    public function __construct($db)
    {
        $this->db = $db;
    }

    public function run_trigger($action, $object, User $user, Translate $langs, Conf $conf)
    {
        // URL de tu sistema de rifas
        $apiUrl = 'https://tudominio.com/raffles/api/dolibarr/webhook/';
        // API Key configurada en el admin de rifas
        $apiKey = 'TU-API-KEY-AQUI';

        // Evento: Validación de Factura
        if ($action == 'BILL_VALIDATE') {

            // Obtener datos del cliente
            $object->fetch_thirdparty();
            $thirdparty = $object->thirdparty;

            // Datos a enviar
            $data = [
                'ref' => $object->ref, // Referencia de la factura (INV-XXX)
                'customer_id' => $thirdparty->id,
                'customer_identification' => $thirdparty->idprof1, // RUC/Cédula (Ajustar según campo usado en Dolibarr: idprof1, idprof2, etc.)
                'customer_name' => $thirdparty->name,
                'customer_email' => $thirdparty->email,
                'customer_phone' => $thirdparty->phone,
                'customer_address' => $thirdparty->address,
                'total_amount' => $object->total_ttc, // Total con impuestos
            ];

            // Enviar petición CURL
            $ch = curl_init($apiUrl);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
            curl_setopt($ch, CURLOPT_HTTPHEADER, [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $apiKey
            ]);

            $response = curl_exec($ch);

            // Opcional: Loguear respuesta en Dolibarr
            // dol_syslog("Raffle Response: " . $response);

            curl_close($ch);
        }

        return 0;
    }
}
```

### Campos Importantes
*   **`customer_identification`**: Es crucial que este campo coincida con la Cédula/RUC del cliente para evitar duplicados. En Dolibarr suele ser `idprof1`, `idprof2`, etc., dependiendo de la localización del país.
*   **`total_amount`**: Usa `total_ttc` para el total con impuestos o `total_ht` para el subtotal antes de impuestos.

## Pruebas
1.  Activa la integración en el admin de Rifas.
2.  Crea una factura en Dolibarr y valídala.
3.  Revisa en el admin de Rifas si se creó el cliente y los boletos correspondientes.
