<?php

namespace WPML\PostHog\Event;

use WPML\Core\Component\PostHog\Application\Service\Config\ConfigService;
use WPML\Core\Component\PostHog\Application\Service\Event\CaptureEventService;
use WPML\Infrastructure\WordPress\Component\PostHog\Application\Cookies\Cookies;
use WPML\Infrastructure\WordPress\Component\PostHog\Application\Repository\PostHogStateRepository;
use WPML\Infrastructure\WordPress\Component\PostHog\Domain\Event\Capture;
use WPML\Infrastructure\WordPress\Port\Persistence\Options;

class CaptureEvent {

	public static function capture( $eventName, $eventProps, $personProps = [] ) {
		$postHogConfig = ( new ConfigService() )->create();

		$postHogStateRepository = new PostHogStateRepository( new Options() );
		$postHogCookies         = new Cookies();
		$postHogCaptureEvent    = new Capture( $postHogStateRepository );

		$postHogCaptureEvent = new CaptureEventService( $postHogStateRepository, $postHogCookies, $postHogCaptureEvent );
		$postHogCaptureEvent->capture(
			$postHogConfig,
			$eventName,
			$eventProps,
			$personProps
		);
	}
}
