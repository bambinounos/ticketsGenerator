<?php
/**
 *  \file       htdocs/raffles/admin/setup.php
 *  \ingroup    raffles
 *  \brief      Setup page for Raffles module
 */

// Load Dolibarr environment
$res = 0;
// Try main.inc.php into web root known defined into CONTEXT_DOCUMENT_ROOT (not always defined)
if (! $res && ! empty($_SERVER["CONTEXT_DOCUMENT_ROOT"])) $res = @include $_SERVER["CONTEXT_DOCUMENT_ROOT"] . "/main.inc.php";
// Try main.inc.php into web root detected using web root calculated from SCRIPT_FILENAME
$tmp = empty($_SERVER["SCRIPT_FILENAME"]) ? '' : $_SERVER["SCRIPT_FILENAME"];
$tmp2 = realpath(__FILE__);
$i = strlen($tmp) - 1;
$j = strlen($tmp2) - 1;
while ($i > 0 && $j > 0 && isset($tmp[$i]) && isset($tmp2[$j]) && $tmp[$i] == $tmp2[$j]) {
	$i--;
	$j--;
}
if (! $res && $i > 0 && file_exists(substr($tmp, 0, ($i + 1)) . "/main.inc.php")) $res = @include substr($tmp, 0, ($i + 1)) . "/main.inc.php";
if (! $res && $res != 1) $res = @include "../../../main.inc.php";
if (! $res && $res != 1) die("Include of main failed");

global $langs, $user;

// Libraries
require_once DOL_DOCUMENT_ROOT . "/core/lib/admin.lib.php";
// require_once "../lib/raffles.lib.php";

// Parameters
$action = GETPOST('action', 'alpha');
$backtopage = GETPOST('backtopage', 'alpha');

// Access control
if (!$user->admin) accessforbidden();

// Load translations
$langs->load("raffles@raffles");
$langs->load("admin");

// Configuration parameters
$conf_RAFFLES_API_URL = GETPOST('RAFFLES_API_URL', 'nohtml');
$conf_RAFFLES_API_KEY = GETPOST('RAFFLES_API_KEY', 'nohtml');

/*
 * Actions
 */

if ($action == 'set_configuration') {
	// CSRF Check
	if (! newTokenCheck()) {
        // Newer Dolibarr versions use newTokenCheck() which checks GETPOST('token') against session
        // For compatibility with older versions (if needed), one might use other methods,
        // but newTokenCheck() is standard in recent versions.
        setEventMessages($langs->trans("ErrorBadCsrfToken"), null, 'errors');
    } else {
		$error = 0;

		if (empty($conf_RAFFLES_API_URL)) {
			setEventMessages($langs->trans("ErrorFieldRequired", $langs->transnoentities("API URL")), null, 'errors');
			$error++;
		}

		if (!$error) {
			$res = dolibarr_set_const($db, "RAFFLES_API_URL", $conf_RAFFLES_API_URL, 'chaine', 0, '', $conf->entity);
			$res = dolibarr_set_const($db, "RAFFLES_API_KEY", $conf_RAFFLES_API_KEY, 'chaine', 0, '', $conf->entity);

			setEventMessages($langs->trans("SetupSaved"), null, 'mesgs');
		}
	}
}

/*
 * View
 */

$form = new Form($db);

$page_name = "RafflesSetup";
llxHeader('', $langs->trans($page_name));

// Subheader
$linkback = '<a href="' . DOL_URL_ROOT . '/admin/modules.php?restore_lastsearch_values=1">' . $langs->trans("BackToModuleList") . '</a>';
print load_fiche_titre($langs->trans($page_name), $linkback, 'title_setup');

// Configuration form
print '<form method="POST" action="' . $_SERVER["PHP_SELF"] . '">';
print '<input type="hidden" name="token" value="' . newToken() . '">';
print '<input type="hidden" name="action" value="set_configuration">';

print '<table class="noborder" width="100%">';
print '<tr class="liste_titre">';
print '<td>' . $langs->trans("Parameters") . '</td>';
print '<td class="right">' . $langs->trans("Value") . '</td>';
print '</tr>';

// API URL
print '<tr class="oddeven">';
print '<td>' . $langs->trans("RafflesApiUrl") . ' <span class="opacitymedium">(e.g. https://tudominio.com/raffles/api/dolibarr/webhook/)</span></td>';
print '<td class="right">';
print '<input type="text" class="minwidth300" name="RAFFLES_API_URL" value="' . (!empty($conf->global->RAFFLES_API_URL) ? $conf->global->RAFFLES_API_URL : '') . '">';
print '</td>';
print '</tr>';

// API KEY
print '<tr class="oddeven">';
print '<td>' . $langs->trans("RafflesApiKey") . '</td>';
print '<td class="right">';
print '<input type="text" class="minwidth300" name="RAFFLES_API_KEY" value="' . (!empty($conf->global->RAFFLES_API_KEY) ? $conf->global->RAFFLES_API_KEY : '') . '">';
print '</td>';
print '</tr>';

print '</table>';

print '<br>';
print '<div class="center">';
print '<input type="submit" class="button" value="' . $langs->trans("Save") . '">';
print '</div>';

print '</form>';

llxFooter();
$db->close();
