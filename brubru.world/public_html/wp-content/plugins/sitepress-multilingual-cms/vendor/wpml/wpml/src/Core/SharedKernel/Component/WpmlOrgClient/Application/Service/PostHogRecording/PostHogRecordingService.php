<?php

namespace WPML\Core\SharedKernel\Component\WpmlOrgClient\Application\Service\PostHogRecording;

use WPML\Core\SharedKernel\Component\WpmlOrgClient\Domain\Api\Endpoints\PostHogRecordingInterface;

class PostHogRecordingService {

  /** @var PostHogRecordingInterface */
  private $postHogRecording;


  public function __construct( PostHogRecordingInterface $postHogRecording ) {
    $this->postHogRecording = $postHogRecording;
  }


  /**
   * @param string $siteKey
   * @param string $recordingMode
   *
   * @return array{
   *   success: bool,
   *   shouldRecord: bool
   * }
   */
  public function run( string $siteKey, string $recordingMode = 'default' ): array {
    return $this->postHogRecording->run( $siteKey, $recordingMode );
  }


}
