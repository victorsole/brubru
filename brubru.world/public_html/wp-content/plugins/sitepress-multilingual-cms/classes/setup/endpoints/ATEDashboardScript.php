<?php

namespace WPML\Setup\Endpoint;

use WPML\Ajax\IHandler;
use WPML\ATE\Proxies\Dashboard;
use WPML\Collect\Support\Collection;
use WPML\FP\Either;
use WPML\FP\Right;
use WPML_TM_AMS_ATE_Console_Section;

class ATEDashboardScript implements IHandler {

	/**
	 * Returns the ATE dashboard script content.
	 *
	 * @param Collection $data
	 *
	 * @return Either
	 */
	public function run( Collection $data ) {
		return Right::of( $this->getAteDashboardScript() );
	}

	/**
	 * Gets the ATE dashboard script content.
	 *
	 * @return string
	 */
	private function getAteDashboardScript() {
		$ate_file = WPML_PLUGIN_PATH . '/res/js/ate-dashboard.php';
		if ( file_exists( $ate_file ) ) {
			$_GET[ Dashboard::QUERY_VAR_ATE_WIDGET_SCRIPT ] = Dashboard::SCRIPT_NAME;
			ob_start();
			include $ate_file;
			return ob_get_clean();
		}
		return '';
	}
}
