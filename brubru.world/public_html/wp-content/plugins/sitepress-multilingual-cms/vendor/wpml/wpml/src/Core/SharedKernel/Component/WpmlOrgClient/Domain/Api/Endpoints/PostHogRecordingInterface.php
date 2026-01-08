<?php

namespace WPML\Core\SharedKernel\Component\WpmlOrgClient\Domain\Api\Endpoints;

interface PostHogRecordingInterface {


  /**
   * @param string $siteKey
   * @param string $recordingMode
   *
   * @return array{
   *   success: bool,
   *   shouldRecord: bool
   * }
   */
  public function run( string $siteKey, string $recordingMode = 'default' ): array;


}
