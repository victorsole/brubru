<?php

namespace WPML\Infrastructure\WordPress\Component\PostHog\Domain\Event;

use WPML\Core\Component\PostHog\Application\Repository\PostHogStateRepositoryInterface;
use WPML\Core\Component\PostHog\Domain\Event\CaptureInterface;

class Capture implements CaptureInterface {

  const POSTHOG_CAPTURE_ENDPOINT = '/i/v0/e/';

  /** @var PostHogStateRepositoryInterface */
  private $postHogStateRepository;


  public function __construct(
    PostHogStateRepositoryInterface $postHogStateRepository
  ) {
    $this->postHogStateRepository = $postHogStateRepository;
  }


  /**
   * Capturing single custom event to PostHog API
   * https://posthog.com/docs/api/capture
   *
   * @param string $apiKey
   * @param string $host
   * @param string $distinctId
   * @param string $eventName
   * @param array<string, mixed> $eventProperties
   * @param array<string, mixed> $personProperties
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
  ): bool {
    if ( ! $this->postHogStateRepository->isEnabled() ) {
      return false;
    }

    if ( ! $distinctId ) {
      return false;
    }

    $properties = $eventProperties;

    if ( ! empty( $personProperties ) ) {
      // "$set" is a reserved key for PostHog that's used to define person properties
      $properties['$set'] = $personProperties;
    }

    $payload = [
      'api_key'     => $apiKey,
      'event'       => $eventName,
      'distinct_id' => $distinctId,
      'properties'  => $properties,
      'timestamp'   => $this->getCurrentTimestamp(),
    ];

    if ( ! $encodedBody = $this->wpJsonEncode( $payload ) ) {
      return false;
    }

    $this->wpRemotePost(
      rtrim( $host, '/' ) . self::POSTHOG_CAPTURE_ENDPOINT,
      [
        'headers'     => [ 'Content-Type' => 'application/json' ],
        'body'        => $encodedBody,
        'blocking'    => false,
        'timeout'     => 1,
        'data_format' => 'body'
      ]
    );

    return true;
  }


  /**
   * Wrapper for wp_json_encode to make testing easier
   *
   * @param mixed $payload
   * @return string|false
   */
  protected function wpJsonEncode( $payload ) {
    return wp_json_encode( $payload );
  }


  /**
   * Wrapper for wp_remote_post to make testing easier
   *
   * @param string $url
   * @param array{
   *   headers: array<string, string>,
   *   body: string,
   *   blocking: bool,
   *   timeout: int,
   *   data_format: string
   * } $args
   * @return mixed
   */
  protected function wpRemotePost( $url, $args ) {
    return wp_remote_post( $url, $args );
  }


  /**
   * Get the current timestamp in ISO 8601 format
   *
   * @return string
   */
  protected function getCurrentTimestamp() {
    return date( 'c' );
  }


}
