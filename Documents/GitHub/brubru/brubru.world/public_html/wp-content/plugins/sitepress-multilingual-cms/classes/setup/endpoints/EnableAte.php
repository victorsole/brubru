<?php

namespace WPML\Setup\Endpoint;

use OTGS\Installer\FP\Either;
use WPML\Ajax\IHandler;
use WPML\Collect\Support\Collection;
use WPML\Setup\Option;
use function WPML\Container\make;

class EnableAte implements IHandler {

	public function run( Collection $data ) {
		if ( ! Option::isTMAllowed() ) {
			return Either::left( __( 'A user does not have a proper license to enable ATE.', 'sitepress' ) );
		}

		if ( \WPML_TM_ATE_Status::is_enabled_and_activated() ) {
			return Either::of( true );
		}
		Option::setTranslateEverythingDefault();
		make( \WPML\TM\ATE\AutoTranslate\Endpoint\EnableATE::class )->run( wpml_collect( [] ) );

		return Either::of( true );
	}


}
