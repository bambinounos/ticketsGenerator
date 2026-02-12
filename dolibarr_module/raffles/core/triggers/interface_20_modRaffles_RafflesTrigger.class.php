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
 * Class InterfaceRafflesTrigger
 *
 * Trigger for Raffles module.
 * Strictly typed for Dolibarr 17+ / PHP 8.
 */
class InterfaceRafflesTrigger extends DolibarrTriggers
{
    /**
     * Constructor
     *
     * @param DoliDB $db Database handler
     */
    public function __construct($db)
    {
        parent::__construct($db);

        $this->name = preg_replace('/^Interface/i', '', get_class($this));
        $this->family = "raffles";
        $this->description = "Trigger para enviar datos a sistema de rifas";
        $this->version = '1.1.0';
    }

    /**
     * Function called when a Dolibarr business event is done.
     * Note: Some Dolibarr versions call run_trigger() instead of runTrigger()
     *
     * @param string        $action Event action code
     * @param object        $object Object
     * @param User          $user   Object user
     * @param Translate     $langs  Object langs
     * @param Conf          $conf   Object conf
     * @return int         <0 if KO, 0 if no triggered ran, >0 if OK
     */
    public function runTrigger($action, $object, User $user, Translate $langs, Conf $conf)
    {
        // PROOF OF LIFE: Log every call to confirm trigger is being executed
        dol_syslog("RafflesTrigger::runTrigger CALLED - action=" . $action, LOG_INFO);

        try {
            // 1. Verificación defensiva de activación del módulo
            // Use OR logic: module is enabled if EITHER signal says enabled
            // This prevents false negatives when one source is unavailable
            $enabledViaConf = isset($conf->raffles) && is_object($conf->raffles) && !empty($conf->raffles->enabled);
            $enabledViaGlobal = !empty($conf->global->MAIN_MODULE_RAFFLES);

            if (!$enabledViaConf && !$enabledViaGlobal) {
                dol_syslog("RafflesTrigger: Module not enabled (conf->raffles->enabled=" . ($enabledViaConf ? '1' : '0') . ", MAIN_MODULE_RAFFLES=" . ($enabledViaGlobal ? '1' : '0') . ")", LOG_DEBUG);
                return 0;
            }

            switch ($action) {
                case 'BILL_VALIDATE':
                    // Extra security check: Ensure the object is actually a Customer Invoice
                    // In v17, checking property existence is critical before access
                    if (!is_object($object) || empty($object->element) || $object->element != 'facture') {
                        return 0;
                    }

                    dol_syslog("RafflesTrigger: Action BILL_VALIDATE detected on Invoice " . (isset($object->ref) ? $object->ref : 'unknown'), LOG_DEBUG);

                    // URL de tu sistema de rifas
                    $apiUrl = !empty($conf->global->RAFFLES_API_URL) ? $conf->global->RAFFLES_API_URL : '';
                    // API Key configurada en el admin de rifas
                    $apiKey = !empty($conf->global->RAFFLES_API_KEY) ? $conf->global->RAFFLES_API_KEY : '';

                    if (empty($apiUrl) || empty($apiKey)) {
                        dol_syslog("RafflesTrigger: API URL or API Key not configured, skipping", LOG_DEBUG);
                        return 0;
                    }

                    if (!function_exists('curl_init')) {
                        dol_syslog("RafflesTrigger Error: CURL extension not available", LOG_ERR);
                        return 0;
                    }

                    // Obtener datos del cliente
                    $thirdparty = null;
                    if (!empty($object->thirdparty) && is_object($object->thirdparty)) {
                        $thirdparty = $object->thirdparty;
                    } elseif (method_exists($object, 'fetch_thirdparty')) {
                        $object->fetch_thirdparty();
                        if (isset($object->thirdparty) && is_object($object->thirdparty)) {
                            $thirdparty = $object->thirdparty;
                        }
                    }

                    if (!is_object($thirdparty)) {
                        dol_syslog("RafflesTrigger: Could not fetch thirdparty for invoice", LOG_WARNING);
                        return 0;
                    }

                    // Datos a enviar - use defensive property access
                    $data = array(
                        'ref' => isset($object->ref) ? $object->ref : '',
                        'facture_id' => isset($object->id) ? $object->id : 0,
                        'customer_id' => isset($thirdparty->id) ? $thirdparty->id : 0,
                        'customer_identification' => !empty($thirdparty->idprof1) ? $thirdparty->idprof1 : (!empty($thirdparty->idprof2) ? $thirdparty->idprof2 : (isset($thirdparty->id) ? $thirdparty->id : '')),
                        'customer_name' => isset($thirdparty->name) ? $thirdparty->name : '',
                        'customer_email' => isset($thirdparty->email) ? $thirdparty->email : '',
                        'customer_phone' => isset($thirdparty->phone) ? $thirdparty->phone : '',
                        'customer_address' => isset($thirdparty->address) ? $thirdparty->address : '',
                        'total_amount' => isset($object->total_ttc) ? $object->total_ttc : 0,
                    );

                    // Enviar petición CURL
                    $ch = curl_init($apiUrl);
                    if ($ch === false) {
                        dol_syslog("RafflesTrigger Error: Failed to initialize CURL", LOG_ERR);
                        return 0;
                    }

                    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                    curl_setopt($ch, CURLOPT_POST, true);
                    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
                    curl_setopt($ch, CURLOPT_HTTPHEADER, array(
                        'Content-Type: application/json',
                        'Authorization: Bearer ' . $apiKey
                    ));

                    curl_setopt($ch, CURLOPT_TIMEOUT, 10);
                    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);

                    $response = curl_exec($ch);
                    $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

                    if (curl_errno($ch)) {
                        dol_syslog("RafflesTrigger Error: " . curl_error($ch), LOG_ERR);
                        setEventMessages("Rifas: Error de conexión - " . curl_error($ch), null, 'errors');
                    } else {
                        $responseData = json_decode($response, true);
                        $logLevel = ($httpcode >= 200 && $httpcode < 300) ? LOG_INFO : LOG_ERR;
                        dol_syslog("RafflesTrigger Response [" . $httpcode . "]: " . $response, $logLevel);
                        
                        if ($httpcode == 200 || $httpcode == 201) {
                            $ticketCount = isset($responseData['tickets_generated']) ? $responseData['tickets_generated'] : 0;
                            $ticketNumbers = isset($responseData['ticket_numbers']) ? implode(', ', $responseData['ticket_numbers']) : '';
                            setEventMessages("Rifas: Se generaron " . $ticketCount . " boleto(s) gratis. Números: " . $ticketNumbers, null, 'mesgs');
                        } elseif ($httpcode == 401) {
                            setEventMessages("Rifas: Error de autenticación - Verifique el API Key en la configuración", null, 'errors');
                        } elseif ($httpcode == 409) {
                            $existingCount = isset($responseData['tickets_previously_generated']) ? $responseData['tickets_previously_generated'] : 0;
                            setEventMessages("Rifas: Esta factura ya generó " . $existingCount . " boleto(s) anteriormente", null, 'warnings');
                        } elseif ($httpcode == 500) {
                            $errorMsg = isset($responseData['error']) ? $responseData['error'] : 'Error desconocido';
                            setEventMessages("Rifas: Error del servidor - " . $errorMsg, null, 'errors');
                        } elseif ($httpcode == 503) {
                            setEventMessages("Rifas: Integración desactivada o sin rifa activa configurada", null, 'warnings');
                        } else {
                            $errorMsg = isset($responseData['error']) ? $responseData['error'] : 'Error desconocido';
                            setEventMessages("Rifas: Error [" . $httpcode . "] - " . $errorMsg, null, 'errors');
                        }
                    }

                    curl_close($ch);
                    break;

                default:
                    break;
            }

            return 0;

        } catch (Throwable $e) {
            // Catch any error/exception to prevent breaking other triggers
            dol_syslog("RafflesTrigger Critical Error: " . $e->getMessage() . " in " . $e->getFile() . ":" . $e->getLine(), LOG_ERR);
            return 0;
        } catch (Exception $e) {
            // Fallback for PHP 5.x compatibility (though we target PHP 7+)
            dol_syslog("RafflesTrigger Exception: " . $e->getMessage(), LOG_ERR);
            return 0;
        }
    }

    /**
     * Alias for runTrigger - some Dolibarr versions call run_trigger() instead
     * This ensures compatibility across different Dolibarr versions
     *
     * @param string        $action Event action code
     * @param object        $object Object
     * @param User          $user   Object user
     * @param Translate     $langs  Object langs
     * @param Conf          $conf   Object conf
     * @return int         <0 if KO, 0 if no triggered ran, >0 if OK
     */
    public function run_trigger($action, $object, User $user, Translate $langs, Conf $conf)
    {
        dol_syslog("RafflesTrigger::run_trigger CALLED (alias) - action=" . $action, LOG_INFO);
        return $this->runTrigger($action, $object, $user, $langs, $conf);
    }
}
