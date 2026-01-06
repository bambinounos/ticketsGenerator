<?php
include_once DOL_DOCUMENT_ROOT . '/core/modules/DolibarrModules.class.php';

/**
 * Class modRaffles
 *
 * Descriptor file for Raffles module
 */
class modRaffles extends DolibarrModules
{
	/**
	 * Constructor. Define names, constants, directories, boxes, permissions
	 *
	 * @param DoliDB $db Database handler
	 */
	public function __construct($db)
	{
		global $conf;

		$this->db = $db;

		// Call parent constructor to initialize defaults
		parent::__construct($db);

		// Id for module (must be unique).
		// Use a random value or a value from a range assigned to the developer
		$this->numero = 600000;

		// Key text used to identify module (for permissions, menus, etc...)
		$this->rights_class = 'raffles';

		// Family can be 'crm', 'financial', 'hr', 'projects', 'products', 'ecm', 'technic', 'other'
		// It is used to group modules in module setup page
		$this->family = 'interface';

		// Module label (no space allowed), used if translation string 'ModuleXXXName' not found (where XXX is value of property name)
		$this->name = preg_replace('/^mod/i', '', get_class($this));

		// Module description, used if translation string 'ModuleXXXDesc' not found (where XXX is value of property name)
		$this->description = "Integración con Sistema de Rifas (Webhook)";

		// Possible values for version are: 'development', 'experimental', 'dolibarr' or version
		$this->version = '1.0.0';

		// Key used in llx_const table to save module setup setup (always 'MAIN_MODULE_' + uppercase(name))
		$this->const_name = 'MAIN_MODULE_' . strtoupper($this->name);

		// Where to store the module in setup page (0=common,1=interface,2=others,3=very specific)
		$this->special = 1;

		// Name of image file used for this module.
		// If file is in theme/yourtheme/img directory, path to file.
		// If file is in module/img directory, path to file.
		$this->picto = 'generic';

		// Defined all module parts (triggers, login, substitutions, menus, css, etc...)
		// for default modules (part=0) or external modules (part=1)
		$this->module_parts = array(
			'triggers' => 1,      // Set this to 1 if module has its own trigger directory
			'login' => 0,
			'substitutions' => 0,
			'menus' => 0,
			'theme' => 0,
			'tpl' => 0,
			'models' => 0,
			'css' => 0,
			'js' => 0,
			'hooks' => array()
		);

		// Config page URL
		$this->config_page_url = array("setup.php@raffles");

		// Dependencies
		$this->depends = array();
		$this->requiredby = array();
		$this->conflictwith = array();
		$this->phpmin = array(7, 0);
		$this->need_dolibarr_version = array(14, 0);
		$this->langfiles = array("raffles@raffles");

		// Constants
		$this->dirs = array();
	}
}
