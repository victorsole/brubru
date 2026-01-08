<?php

namespace WPML\TM\ATE;

use WPML\ATE\Proxies\ProxyInterceptorLoader;
use WPML_TM_ATE_AMS_Endpoints;

class ATEDashboardLoader {
	const ATE_DASHBOARD_ID = 'eate_dashboard';

	/**
	 * @var ProxyInterceptorLoader
	 */
	private $proxy;
	/**
	 * @var WPML_TM_ATE_AMS_Endpoints
	 */
	private $endpoints;

	function __construct( ProxyInterceptorLoader $proxy, WPML_TM_ATE_AMS_Endpoints $endpoints ) {
		$this->proxy     = $proxy;
		$this->endpoints = $endpoints;
	}


	public function registerScript() {
		if ( $this->proxy->shouldEnableProxy() ) {
			return self::registerScriptUsingProxy();
		} else {
			return self::registerScriptWithoutProxy();
		}
	}

	public function initializeScript( $params ) {
		// Create a unique handle for the initializer script
		$initializer_handle = self::ATE_DASHBOARD_ID . '-init';

		// Register and enqueue the initializer script with the dashboard script as a dependency
		wp_register_script( $initializer_handle, '', [ self::ATE_DASHBOARD_ID ], ICL_SITEPRESS_SCRIPT_VERSION, true );
		wp_enqueue_script( $initializer_handle );

		// Initialize the script after the page is fully loaded to ensure all scripts are ready to listen for events
		wp_add_inline_script( $initializer_handle, 'window.addEventListener("load", function() {window.ateDashboard(' . wp_json_encode( $params ) . '); });' );
	}

	private function registerScriptUsingProxy() {
		$handle = self::ATE_DASHBOARD_ID;
		$this->proxy->enqueueJS(
			$handle,
			$this->getATEDashboardUrl(), [ ProxyInterceptorLoader::HANDLE_JS ], ICL_SITEPRESS_SCRIPT_VERSION );

		return $handle;
	}

	private function registerScriptWithoutProxy() {
		$handle    = self::ATE_DASHBOARD_ID;
		$src       = $this->getATEDashboardUrl();
		$deps      = []; // Add any dependencies the script might have
		$in_footer = true; // Load the script in the footer for better performance
		wp_register_script( self::ATE_DASHBOARD_ID, $src, $deps, ICL_SITEPRESS_SCRIPT_VERSION, $in_footer );
		wp_enqueue_script( $handle );

		return $handle;
	}

	private function getATEDashboardUrl() {
		return $this->endpoints->get_ate_dashboard_url();
	}
}
