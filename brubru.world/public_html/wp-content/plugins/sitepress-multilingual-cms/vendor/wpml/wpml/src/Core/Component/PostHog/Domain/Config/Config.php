<?php

namespace WPML\Core\Component\PostHog\Domain\Config;

class Config {

  // Default API KEY for the "WPML Plugins" project on PostHog dashboard.
  const DEFAULT_API_KEY = 'phc_UUIWtbxYIro1TjT0zROVCJA2heo5jGOlYsn2NV2Fm6A';
  const DEFAULT_HOST = 'https://us.i.posthog.com';
  const DEFAULT_DISABLE_SURVEYS = true;
  const DEFAULT_AUTO_CAPTURE = false;
  const DEFAULT_CAPTURE_PAGE_VIEW = false;
  const DEFAULT_CAPTURE_PAGE_LEAVE = false;
  const DEFAULT_DISABLE_SESSION_RECORDING = false;

  // or 'always' to create profiles for anonymous users as well
  const DEFAULT_PERSON_PROFILES = 'identified_only';

  /** @var string */
  private $apiKey;

  /** @var string */
  private $host;

  /** @var string */
  private $personProfiles;

  /** @var bool */
  private $disableSurveys;

  /** @var bool */
  private $autoCapture;

  /** @var bool */
  private $capturePageView;

  /** @var bool */
  private $capturePageLeave;

  /** @var bool */
  private $disableSessionRecording;


  public function __construct(
    string $apiKey,
    string $host,
    string $personProfiles,
    bool $disableSurveys,
    bool $autoCapture,
    bool $capturePageView,
    bool $capturePageLeave,
    bool $disableSessionRecording
  ) {
    $this->apiKey                  = $apiKey;
    $this->host                    = $host;
    $this->personProfiles          = $personProfiles;
    $this->disableSurveys          = $disableSurveys;
    $this->autoCapture             = $autoCapture;
    $this->capturePageView         = $capturePageView;
    $this->capturePageLeave        = $capturePageLeave;
    $this->disableSessionRecording = $disableSessionRecording;
  }


  /** @return void */
  public function setApiKey( string $apiKey ) {
    $this->apiKey = $apiKey;
  }


  /** @return void */
  public function setHost( string $host ) {
    $this->host = $host;
  }


  /** @return void */
  public function setDisableSurveys( bool $disableSurveys ) {
    $this->disableSurveys = $disableSurveys;
  }


  /** @return void */
  public function setAutoCapture( bool $autoCapture ) {
    $this->autoCapture = $autoCapture;
  }


  /** @return void */
  public function setCapturePageView( bool $capturePageView ) {
    $this->capturePageView = $capturePageView;
  }


  /** @return void */
  public function setCapturePageLeave( bool $capturePageLeave ) {
    $this->capturePageLeave = $capturePageLeave;
  }


  /** @return void */
  public function setDisableSessionRecording( bool $disableSessionRecording ) {
    $this->disableSessionRecording = $disableSessionRecording;
  }


  /** @return void */
  public function setPersonProfiles( string $personProfiles ) {
    $this->personProfiles = $personProfiles;
  }


  public function getApiKey(): string {
    return $this->apiKey;
  }


  public function getHost(): string {
    return $this->host;
  }


  public function getPersonProfiles(): string {
    return $this->personProfiles;
  }


  public function getDisableSurveys(): bool {
    return $this->disableSurveys;
  }


  public function getAutoCapture(): bool {
    return $this->autoCapture;
  }


  public function getCapturePageView(): bool {
    return $this->capturePageView;
  }


  public function getCapturePageLeave(): bool {
    return $this->capturePageLeave;
  }


  public function getDisableSessionRecording(): bool {
    return $this->disableSessionRecording;
  }


}
