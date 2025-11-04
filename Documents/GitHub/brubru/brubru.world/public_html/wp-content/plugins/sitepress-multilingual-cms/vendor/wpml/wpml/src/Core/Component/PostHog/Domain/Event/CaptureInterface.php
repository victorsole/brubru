<?php

namespace WPML\Core\Component\PostHog\Domain\Event;

interface CaptureInterface {


  /**
   * @param string $apiKey
   * @param string $host
   * @param string $distinctId
   * @param string $eventName
   * @param array<string, mixed> $eventProperties
   * @param array<string,mixed> $personProperties
   *
   * @return bool
   */
  public function capture(
    string $apiKey,
    string $host,
    string $distinctId,
    string $eventName,
    array $eventProperties,
    array $personProperties = []
  ): bool;


}
