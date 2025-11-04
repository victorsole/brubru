<?php

namespace WPML\TM\Troubleshooting;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Application\Service\MigrationStatus\MigrationStatusService;
use WPML\LIB\WP\Nonce;
use WPML\Core\WP\App\Resources;
use WPML\TM\ATE\AutoTranslate\Endpoint\CancelJobs;
use WPML\TM\ATE\ClonedSites\Lock;
use WPML\LanguageSwitcher\LsTemplateDomainUpdater;
use WPML\TM\Troubleshooting\Endpoints\OptimizeDbTables\Endpoint;
use WPML\TM\Troubleshooting\Endpoints\RetryStuckAutomaticJobs\RequestHandler;
use WPML\Setup\Option;

class Loader implements \IWPML_Backend_Action {

	public function add_hooks() {

		add_action( 'after_setup_complete_troubleshooting_functions', [ $this, 'render' ], 7 );
		add_action( 'admin_enqueue_scripts', [ $this, 'enqueueScripts' ] );
	}

	public function render() {
		echo '<div id="wpml-troubleshooting-container" style="margin: 5px 0;"></div>';
	}

	public function enqueueScripts( $hook ) {
		if ( WPML_PLUGIN_FOLDER . '/menu/troubleshooting.php' === $hook ) {
			global $wpml_dic;
			/** @var MigrationStatusService $migrationStatusService */
			$migrationStatusService = $wpml_dic->make( MigrationStatusService::class );
			$migrationStatus        = $migrationStatusService->getMigrationStatus();

			$enqueue = Resources::enqueueApp( 'troubleshooting' );
			$enqueue(
				[
					'name' => 'troubleshooting',
					'data' => [
						'refreshLicense' => [
							'nonce' => Nonce::create( 'update_site_key_wpml' ),
						],
						'doTranslationTablesRequireOptimization' => ! $migrationStatus->isTotalProcessCompleted(),
						'isATELocked'    => Lock::isLocked(),
						'isTEAEnabled'   => Option::shouldTranslateEverything(),
						'endpoints'      => [
							'cancelJobs'                => CancelJobs::class,
							'lsTemplatesUpdateDomain'   => LsTemplateDomainUpdater::class,
							'optimizeTranslationTables' => Endpoint::class,
							'retryStuckAutomaticJobs'   => RequestHandler::class,
						],
					],
				]
			);
		}
	}
}
