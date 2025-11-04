<?php
$app         = '';
$constructor = '';
$isJs        = false;
$errors      = [];
$response    = [];

$tryFromCache = false;

if ( isset( $_GET['section'] ) && $_GET['section'] === WPML_TM_AMS_Translation_Quality_Console_Section::SLUG ) {
	$factory           = new WPML_TM_AMS_Translation_Quality_Console_Section_Factory();
	$ateConsoleSection = $factory->create();

	$tryFromCache = true; // try to fetch from cache for translation quality
} else {
	$factory           = new WPML_TM_AMS_ATE_Console_Section_Factory();
	$ateConsoleSection = $factory->create();
}

$appData = $ateConsoleSection->getAppData( $tryFromCache);

$app         = $appData['app'];
$constructor = $appData['constructor'];
$isJs        = $appData['isJs'];
$errors      = $appData['errors'];
$response    = $appData['response'];

foreach ( $appData['headers'] as $header ) {
	header( $header );
}

if ( WP_DEBUG ) {
	if ( count( $errors ) > 0 ) {
		$errors[] = ':: URL:' . PHP_EOL . PHP_EOL . $ateConsoleSection->getWidgetScriptUrl();
		if ( is_wp_error( $response ) ) {
			$errors[] = ':: Error:' . PHP_EOL . PHP_EOL . var_export( $response, true );
		} else {
			$errors[] = ':: Response:' . PHP_EOL . PHP_EOL . var_export( $response['response'], true );
		}
	}

	if ( $errors ) {

		if ( $isJs ) {
			echo '/** ' . PHP_EOL;
		}

		echo join( PHP_EOL . PHP_EOL, $errors );

		if ( $isJs ) {
			echo '*/' . PHP_EOL;
		}
	}

}

if ( ! $errors ) {
	echo <<<WIDGET_CONSTRUCTOR
$app

var params = $constructor;

if( typeof ate_jobs_sync.ateCallbacks.retranslation === 'function' ) {
	params.onGlossaryRetranslationStart = ate_jobs_sync.ateCallbacks.retranslation
}

if( typeof ate_jobs_sync.ateCallbacks.invalidateCache === 'function' ) {
	params.onLanguageMappingChange = ate_jobs_sync.ateCallbacks.invalidateCache
}

LoadRealEateWidget(params);

WIDGET_CONSTRUCTOR;
}
