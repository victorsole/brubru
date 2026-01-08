<?php

namespace WPML\Core\Component\PostHog\Application\Service\Config;

use WPML\Core\Component\PostHog\Domain\Config\Config;

class ConfigService {


  public function create(
    string $apiKey = Config::DEFAULT_API_KEY,
    string $host = Config::DEFAULT_HOST,
    string $personProfiles = Config::DEFAULT_PERSON_PROFILES,
    bool $disableSurveys = Config::DEFAULT_DISABLE_SURVEYS,
    bool $autoCapture = Config::DEFAULT_AUTO_CAPTURE,
    bool $capturePageView = Config::DEFAULT_CAPTURE_PAGE_VIEW,
    bool $capturePageLeave = Config::DEFAULT_CAPTURE_PAGE_LEAVE,
    bool $disableSessionRecording = Config::DEFAULT_DISABLE_SESSION_RECORDING
  ): Config {
    return new Config(
      $apiKey,
      $host,
      $personProfiles,
      $disableSurveys,
      $autoCapture,
      $capturePageView,
      $capturePageLeave,
      $disableSessionRecording
    );
  }


}
