<?php

namespace WPML\UserInterface\Web\Core\Component\Troubleshooting\Application\Endpoint;

use WPML\Core\Component\PostHog\Application\Repository\PostHogStateRepositoryInterface;
use WPML\Core\Port\Endpoint\EndpointInterface;
use WPML\Core\SharedKernel\Component\WpmlOrgClient\Application\Service\PostHogRecording\PostHogRecordingService;

class UpdatePostHogStateController implements EndpointInterface {

  /** @var PostHogStateRepositoryInterface */
  private $posthogStateRepository;

  /** @var PostHogRecordingService */
  private $postHogRecordingService;


  public function __construct(
    PostHogStateRepositoryInterface $posthogStateRepository,
    PostHogRecordingService $postHogRecordingService
  ) {
    $this->posthogStateRepository  = $posthogStateRepository;
    $this->postHogRecordingService = $postHogRecordingService;
  }


  /**
   * Handle the request to update the PostHog state
   *
   * @param array<string, mixed>|null $requestData The request data containing the enabled state
   *
   * @return array{
   *   success: bool,
   *   data: array{
   *   message: string,
   *   enabled: bool,
   *   }
   * } Response data
   */
  public function handle( $requestData = null ): array {
    if (
      ! isset( $requestData['enabled'] ) ||
      ! isset( $requestData['siteKey'] ) ||
      ! is_bool( $requestData['enabled'] ) ||
      ! is_string( $requestData['siteKey'] )
    ) {
      return [
        'success' => false,
        'data'    => [
          'message' => 'Invalid request data',
          'enabled' => false,
        ]
      ];
    }

    $result = $this->postHogRecordingService->run(
      $requestData['siteKey'],
      $requestData['enabled'] ? 'force_enable' : 'force_disable'
    );

    // Update the option in the wp_options table
    $this->posthogStateRepository->setIsEnabled( $result['shouldRecord'] );

    return [
      'success' => true,
      'data'    => [
        'message' => 'PostHog state updated',
        'enabled' => $result['shouldRecord']
      ]
    ];
  }


}
