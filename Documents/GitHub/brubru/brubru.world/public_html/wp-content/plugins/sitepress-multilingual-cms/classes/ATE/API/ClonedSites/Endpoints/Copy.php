<?php

namespace WPML\TM\ATE\ClonedSites\Endpoints;

use WPML\Ajax\IHandler;
use WPML\Collect\Support\Collection;
use WPML\FP\Either;
use WPML\TM\ATE\ClonedSites\Report;
use function WPML\Container\make;

class Copy implements IHandler {

	public function run( Collection $data ) {
		/** @var Report $report */
		$report = make( Report::class );

		$result = $report->copy();

		if ( $result ) {
			do_action( 'wpml_tm_cloned_site_reported', $result );
			return Either::of( true );
		}

		return Either::left( 'Failed to report' );
	}

}
