<?php

namespace WPML\Translation;

use WPML\Core\Component\Translation\Application\Service\PreviousState\PreviousStateService;

class PreviousStateServiceFactory {
	/** @var PreviousStateService|null */
	private static $instance = null;

	public static function create(): PreviousStateService {
		// Check if the instance is already created
		if ( self::$instance === null ) {
			self::$instance = self::createNewInstance();
		}

		// Return the cached instance
		return self::$instance;
	}

	/**
	 * Set a custom instance of PreviousStateService. The main purpose it to mock it in the tests
	 *
	 * @param PreviousStateService $instance
	 *
	 * @return void
	 */
	public static function setService( PreviousStateService $instance ) {
		self::$instance = $instance;
	}

	/**
	 * Create a new instance of PreviousStateService
	 *
	 * @return PreviousStateService
	 */
	private static function createNewInstance(): PreviousStateService {
		global $wpml_dic;

		return $wpml_dic->make( PreviousStateService::class );
	}
}