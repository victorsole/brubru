<?php

namespace WPML\Infrastructure\WordPress\SharedKernel\WpmlOrgClient\Domain\Api\Endpoints\PostHogRecording;

class RecordingModes {

  const DEFAULT = 'default';
  const FORCE_ENABLE = 'force_enable';

  const FORCE_DISABLE = 'force_disable';


  /**
   * @return string[]
   */
  public static function getAll(): array {
    return [
      self::DEFAULT,
      self::FORCE_ENABLE,
      self::FORCE_DISABLE
    ];
  }


}
