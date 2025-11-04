<?php

namespace WPML\Translation;

use WPML\Core\Component\Translation\Application\Service\CompletedTranslationService;

class CompletedTranslationServiceFactory {
	/** @var CompletedTranslationService|null */
	private static $instance = null;

	public static function create(): CompletedTranslationService {
		// Check if the instance is already created
		if ( self::$instance === null ) {
			self::$instance = self::createNewInstance();
		}

		// Return the cached instance
		return self::$instance;
	}

	/**
	 * Set a custom instance of CompletedTranslationService. The main purpose it to mock it in the tests
	 *
	 * @param CompletedTranslationService $instance
	 *
	 * @return void
	 */
	public static function setService( CompletedTranslationService $instance ) {
		self::$instance = $instance;
	}

	/**
	 * Create a new instance of CompletedTranslationService
	 *
	 * @return CompletedTranslationService
	 */
	private static function createNewInstance(): CompletedTranslationService {
		global $wpml_dic;

		return $wpml_dic->make( CompletedTranslationService::class );
	}
}
