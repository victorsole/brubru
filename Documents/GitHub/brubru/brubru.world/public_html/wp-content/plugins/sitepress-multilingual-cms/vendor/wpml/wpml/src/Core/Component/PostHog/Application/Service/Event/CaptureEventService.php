<?php

namespace WPML\Core\Component\PostHog\Application\Service\Event;

use WPML\Core\Component\PostHog\Application\Cookies\CookiesInterface;
use WPML\Core\Component\PostHog\Application\Repository\PostHogStateRepositoryInterface;
use WPML\Core\Component\PostHog\Domain\Config\Config;
use WPML\Core\Component\PostHog\Domain\Event\CaptureInterface;

class CaptureEventService {

  /** @var PostHogStateRepositoryInterface */
  private $postHogStateRepository;

  /** @var CookiesInterface */
  private $cookies;

  /** @var CaptureInterface */
  private $captureEvent;


  public function __construct(
    PostHogStateRepositoryInterface $postHogStateRepository,
    CookiesInterface $cookies,
    CaptureInterface $captureEvent
  ) {
    $this->postHogStateRepository = $postHogStateRepository;
    $this->cookies                = $cookies;
    $this->captureEvent           = $captureEvent;
  }


  /**
   * @param Config $config
   * @param string $eventName
   * @param array<string, mixed> $eventProperties
   * @param array<string, mixed> $personProperties
   *
   * @return bool
   */
  public function capture(
    Config $config,
    string $eventName,
    array $eventProperties,
    array $personProperties = []
  ): bool {
    if ( ! $this->postHogStateRepository->isEnabled() ) {
      return false;
    }

    $apiKey     = $config->getApiKey();
    $host       = $config->getHost();
    $distinctId = $this->cookies->getDistinctId();

    if ( ! $distinctId ) {
      return false;
    }

    return $this->captureEvent->capture(
      $apiKey,
      $host,
      $distinctId,
      $eventName,
      $eventProperties,
      $personProperties
    );
  }


}
