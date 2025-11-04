<?php

namespace WPML\Infrastructure\WordPress\SharedKernel\WpmlOrgClient\Domain\Api\Endpoints\PostHogRecording;

use WPML\Core\SharedKernel\Component\WpmlOrgClient\Domain\Api\ApiUrl;
use WPML\Core\SharedKernel\Component\WpmlOrgClient\Domain\Api\Endpoints\PostHogRecordingInterface;

class PostHogRecording implements PostHogRecordingInterface {

  const ENDPOINT = '/?action=should_record_site';

  /** @var ApiUrl */
  private $apiUrl;


  public function __construct( ApiUrl $apiUrl ) {
    $this->apiUrl = $apiUrl;
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
    $response = wp_remote_post(
      $this->apiUrl->get() . self::ENDPOINT,
      [
        'body' => [
          'site_key'       => $siteKey,
          'recording_mode' => $recordingMode
        ],
      ]
    );

    if ( is_wp_error( $response ) ) {
      return [
        'success'      => false,
        'shouldRecord' => $recordingMode === RecordingModes::FORCE_ENABLE,
      ];
    }

    $responseCode = wp_remote_retrieve_response_code( $response );
    $body         = wp_remote_retrieve_body( $response );
    $decodedBody  = json_decode( $body, true );

    if ( $responseCode !== 200 || ! is_array( $decodedBody ) ) {
      return [
        'success'      => false,
        'shouldRecord' => $recordingMode === RecordingModes::FORCE_ENABLE,
      ];
    }

    return [
      'success'      => true,
      'shouldRecord' => boolval( $decodedBody['should_record'] ),
    ];
  }


}
