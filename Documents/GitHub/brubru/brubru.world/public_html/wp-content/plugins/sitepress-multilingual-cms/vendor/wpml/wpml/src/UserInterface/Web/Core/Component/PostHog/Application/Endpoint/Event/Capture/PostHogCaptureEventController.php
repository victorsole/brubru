<?php

namespace WPML\UserInterface\Web\Core\Component\PostHog\Application\Endpoint\Event\Capture;

use WPML\Core\Component\PostHog\Application\Service\Config\ConfigService;
use WPML\Core\Component\PostHog\Application\Service\Event\CaptureEventService;
use WPML\Core\Port\Endpoint\EndpointInterface;

class PostHogCaptureEventController implements EndpointInterface {

  /** @var ConfigService */
  private $configService;

  /** @var CaptureEventService */
  private $captureEventService;


  public function __construct(
    ConfigService $configService,
    CaptureEventService $captureEventService
  ) {
    $this->configService       = $configService;
    $this->captureEventService = $captureEventService;
  }


  /**
   * @psalm-suppress MoreSpecificImplementedParamType
   *
   * @param array{
   *   eventName: string,
   *   eventProps: array<string, mixed>,
   *   personProps?: array<string, mixed>,
   * }|null $requestData
   *
   * @return array{
   *   success: bool,
   *   message: string,
   * }
   */
  public function handle( $requestData = null ): array {
    if (
      ! is_array( $requestData ) ||
      ! array_key_exists( 'eventName', $requestData ) ||
      ! array_key_exists( 'eventProps', $requestData )
    ) {
      return [
        'success' => false,
        'message' => 'Invalid request data'
      ];
    }

    $personProperties = [];

    /**
     * @psalm-suppress RedundantConditionGivenDocblockType
     */
    if (
      array_key_exists( 'personProps', $requestData ) &&
      is_array( $requestData['personProps'] )
    ) {
      $personProperties = $requestData['personProps'];
    }

    $config = $this->configService->create();

    $result = $this->captureEventService->capture(
      $config,
      $requestData['eventName'],
      $requestData['eventProps'],
      $personProperties
    );

    return [
      'success' => $result,
      'message' => $result ? 'Event captured successfully' : 'Failed to capture event'
    ];
  }


}
