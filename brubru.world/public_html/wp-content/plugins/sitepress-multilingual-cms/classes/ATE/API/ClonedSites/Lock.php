<?php


namespace WPML\TM\ATE\ClonedSites;

use WPML\FP\Obj;
use WPML\TM\ATE\API\FingerprintGenerator;
use function WPML\Container\make;

class Lock {
	const CLONED_SITE_OPTION = 'otgs_wpml_tm_ate_cloned_site_lock';

	/** @var FingerprintGenerator */
	private static $fingerprint_generator;

	public function lock( $lockData ) {
		if ( $this->isLockDataPresent( $lockData ) ) {
			update_option(
				self::CLONED_SITE_OPTION,
				[
					'stored_fingerprint'            => $lockData['stored_fingerprint'],
					'received_fingerprint'          => $lockData['received_fingerprint'],
					'fingerprint_confirmed'         => $lockData['fingerprint_confirmed'],
					'identical_url_before_movement' => isset( $lockData['identical_url_before_movement'] ) ? $lockData['identical_url_before_movement'] : false,
				],
				'no'
			);
		}
	}

	/**
	 * @return array{urlCurrentlyRegisteredInAMS: string, urlUsedToMakeRequest: string, siteMoved: bool}
	 */
	public function getLockData() {
		$option = get_option( self::CLONED_SITE_OPTION, [] );

		$urlUsedToMakeRequest = Obj::propOr(
			'',
			'wp_url',
			is_string( $option['received_fingerprint'] ) ? json_decode( $option['received_fingerprint'] ) : $option['received_fingerprint']
		);

		$urlCurrentlyRegisteredInAMS = Obj::pathOr( '', [ 'stored_fingerprint', 'wp_url' ], $option );

		return [
			'urlCurrentlyRegisteredInAMS' => $urlCurrentlyRegisteredInAMS,
			'urlUsedToMakeRequest'        => $urlUsedToMakeRequest,
			'identicalUrlBeforeMovement'  => Obj::propOr( false, 'identical_url_before_movement', $option ),
		];
	}

	/**
	 * @return string
	 */
	public function getUrlRegisteredInAMS() {
		$lockData = $this->getLockData();

		return $lockData['urlCurrentlyRegisteredInAMS'];
	}

	private function isLockDataPresent( $lockData ) {
		return isset( $lockData['stored_fingerprint'] )
		       && isset( $lockData['received_fingerprint'] )
		       && isset( $lockData['fingerprint_confirmed'] );
	}

	public function unlock() {
		static::doUnlock();
	}

	private static function doUnlock() {
		delete_option( self::CLONED_SITE_OPTION );
	}

	public static function isLocked() {
		$option = get_option( self::CLONED_SITE_OPTION, false );

		if ( $option && isset( $option['stored_fingerprint'] ) && isset( $option['stored_fingerprint']['wp_url'] ) ) {
			$stored_url = $option['stored_fingerprint']['wp_url'];

			// Use FingerprintGenerator to get current URL.
			$current_url = self::getFingerPrintGenerator()->getClonedSiteUrl();

			if ( $stored_url === $current_url ) {
				// URLs match - this is the original site, so we should unlock it.
				static::doUnlock();
				return false;
			}
		}

		return (bool) $option && \WPML_TM_ATE_Status::is_enabled();
	}

	private static function getFingerPrintGenerator() {
		if ( ! self::$fingerprint_generator ) {
			self::$fingerprint_generator = make( FingerprintGenerator::class );
		}
		return self::$fingerprint_generator;
	}

}
