<?php

namespace WPML\Setup\Endpoint;

use Exception;
use WPML\Ajax\IHandler;
use WPML\Collect\Support\Collection;
use WPML\FP\Either;
use WPML\FP\Right;
use WPML_TM_AMS_ATE_Console_Section;
use WPML_TM_AMS_ATE_Console_Section_Factory;

class GetParametersForAteDashboard implements IHandler {

	/**
	 * Returns the ATE dashboard script content.
	 *
	 * @param Collection $data
	 *
	 * @return Either
	 */
	public function run( Collection $data ) {
		return Right::of( self::getParametersForAteDashboard() );
	}


	private function getParametersForAteDashboard() {
		$factory = new WPML_TM_AMS_ATE_Console_Section_Factory();

		/** @var WPML_TM_AMS_ATE_Console_Section|null $ateConsoleSection */
		$ateConsoleSection = $factory->create();


		if ( ! $ateConsoleSection ) {
			throw new Exception( 'ATE is not enabled for this client.' );
		}

		$ateParams = $ateConsoleSection->get_ams_constructor();
		if ( ! isset( $ateParams['shared_key'] ) || empty( $ateParams['shared_key'] ) ) {
			throw new Exception( 'Ate parameters are invalid.' );
		}

		return $ateParams;
	}
}
