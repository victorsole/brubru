<?php

namespace WPML\TM\Upgrade\Commands;

use WPML\Media\Option;
use function WPML\Container\make;
use WPML\Core\BackgroundTask\Service\BackgroundTaskService;

class EnableHandleMediaAutoOptionForNewInstalls implements \IWPML_Upgrade_Command {

	public function run() {
		$startWpmlVersion  = get_option( \WPML_Installation::WPML_START_VERSION_KEY );
		$isNewInstallation = ICL_SITEPRESS_VERSION === $startWpmlVersion;
		$is_st_disabled    = ! defined( 'WPML_ST_VERSION' );
		if ( ! $isNewInstallation || $is_st_disabled ) {
			Option::setShouldShowHandleMediaAutoBannerAfterUpgrade();
			Option::setShouldShowHandleMediaAutoNotice30DaysAfterUpgrade();
			return true;
		}

		$backgroundTaskService = make( BackgroundTaskService::class );
		$endpoint              = make( \WPML\TM\Settings\ProcessExistingMediaInPosts::class );

		Option::setShouldHandleMediaAuto( true );
		$backgroundTaskService->add( $endpoint, wpml_collect( [] ) );

		return true;
	}

	public function run_admin() {
		return $this->run();
	}

	public function run_ajax() {
		return null;
	}

	public function run_frontend() {
		return null;
	}

	public function get_results() {
		return true;
	}
}