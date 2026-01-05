<?php
/* Copyright (C) 2024      Jules
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3 of the License, or
 * (at your option) any later version.
 */

/**
 *  \file       htdocs/raffles/core/triggers/interface_20_modRaffles_RafflesTrigger.class.php
 *  \ingroup    raffles
 *  \brief      Trigger for Raffles module
 */

require_once DOL_DOCUMENT_ROOT . '/core/triggers/dolibarrtriggers.class.php';

/**
 * Class interface_20_modRaffles_RafflesTrigger
 *
 * Trigger for Raffles module
 */
class interface_20_modRaffles_RafflesTrigger extends DolibarrTriggers
{
    public $family = 'raffles';
    public $description = "Trigger para enviar datos a sistema de rifas";
    public $version = '1.0.0';
    public $picto = 'raffles@raffles';

    /**
     * Constructor
     *
     * @param DoliDB $db Database handler
     */
    public function __construct($db)
    {
        $this->db = $db;

        $this->name = preg_replace('/^interface_([0-9]+)_([^_]+)_(.+)$/i', '\\3', get_class($this));
        $this->family = "raffles";
        $this->description = "Trigger para enviar datos a sistema de rifas";
        $this->version = '1.0.0';
    }

    /**
     * Function called when a Dolibarrr business event is done.
     * All functions "run_trigger" are triggered if file is inside triggers folder.
     *
     * @param string    $action Event action code
     * @param object    $object Object
     * @param User      $user   Object user
     * @param Translate $langs  Object langs
     * @param Conf      $conf   Object conf
     * @return int              <0 if KO, 0 if no triggered ran, >0 if OK
     */
    public function run_trigger($action, $object, $user, $langs, $conf)
    {
        // Fail fast if not the target action.
        if ($action != 'BILL_VALIDATE') {
            return 0;
        }

        // Wrap everything else in a try-catch to prevent crashing Dolibarr on any error
        try {
            // Ensure conf is an object before accessing it
            if (!is_object($conf)) {
                return 0;
            }

            // Check if module is enabled
            if (!isset($conf->raffles) || empty($conf->raffles->enabled)) return 0;

            // Extra security check: Ensure the object is actually a Customer Invoice
            if (!is_object($object) || !isset($object->element) || $object->element != 'facture') {
                 return 0;
            }

            // URL de tu sistema de rifas
            $apiUrl = !empty($conf->global->RAFFLES_API_URL) ? $conf->global->RAFFLES_API_URL : '';
            // API Key configurada en el admin de rifas
            $apiKey = !empty($conf->global->RAFFLES_API_KEY) ? $conf->global->RAFFLES_API_KEY : '';

            if (empty($apiUrl) || empty($apiKey)) {
                // Configuration not set
                return 0;
            }

            // Check if curl exists
            if (!function_exists('curl_init')) {
                dol_syslog("RafflesTrigger Error: CURL extension not available", LOG_ERR);
                return 0;
            }

            dol_syslog("RafflesTrigger: Action BILL_VALIDATE detected on Invoice " . (isset($object->ref) ? $object->ref : 'unknown'), LOG_DEBUG);

            // Obtener datos del cliente
            // MODIFICATION: Check if thirdparty is already loaded to avoid reloading it and potentially overwriting changes made by other modules
            $thirdparty = null;
            if (is_object($object)) {
                if (!empty($object->thirdparty) && is_object($object->thirdparty)) {
                     $thirdparty = $object->thirdparty;
                } elseif (method_exists($object, 'fetch_thirdparty')) {
                     $object->fetch_thirdparty();
                     $thirdparty = $object->thirdparty;
                }
            }

            if (!is_object($thirdparty)) {
                 return 0;
            }

            // Datos a enviar
            $data = array(
                'ref' => isset($object->ref) ? $object->ref : '',
                'customer_id' => $thirdparty->id,
                'customer_identification' => !empty($thirdparty->idprof1) ? $thirdparty->idprof1 : (!empty($thirdparty->idprof2) ? $thirdparty->idprof2 : $thirdparty->id),
                'customer_name' => $thirdparty->name,
                'customer_email' => $thirdparty->email,
                'customer_phone' => $thirdparty->phone,
                'customer_address' => $thirdparty->address,
                'total_amount' => isset($object->total_ttc) ? $object->total_ttc : 0,
            );

            // Enviar petición CURL
            $ch = curl_init($apiUrl);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
            curl_setopt($ch, CURLOPT_HTTPHEADER, array(
                'Content-Type: application/json',
                'Authorization: Bearer ' . $apiKey
            ));

            // Timeout to prevent hanging Dolibarr
            curl_setopt($ch, CURLOPT_TIMEOUT, 5);
            curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);

            $response = curl_exec($ch);
            $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

            if (curl_errno($ch)) {
                dol_syslog("RafflesTrigger Error: " . curl_error($ch), LOG_ERR);
            } else {
                dol_syslog("RafflesTrigger Response [" . $httpcode . "]: " . $response, LOG_INFO);
            }

            curl_close($ch);

        } catch (\Throwable $e) {
            // Log the exception but do not stop the process
            dol_syslog("RafflesTrigger Critical Error: " . $e->getMessage(), LOG_ERR);
            return 0;
        }

        return 0;
    }
}
