<?php

namespace WPML\TM\Troubleshooting\Endpoints\OptimizeDbTables;

use WPML\Ajax\IHandler;
use WPML\Collect\Support\Collection;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Application\Service\EntryPointService;
use WPML\FP\Either;

class Endpoint implements IHandler {


	public function run( Collection $data ) {
		global $wpml_dic;

		$service   = $wpml_dic->make( EntryPointService::class );
		$isInitialRequest = $data->get( 'isInitialRequest', false );
		$remaining = $service->run( $data->get( 'migrationType' ), $isInitialRequest );

		return Either::of( $remaining );
	}


}