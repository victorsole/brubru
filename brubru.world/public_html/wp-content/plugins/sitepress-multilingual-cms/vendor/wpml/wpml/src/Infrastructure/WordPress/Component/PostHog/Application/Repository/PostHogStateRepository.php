<?php

namespace WPML\Infrastructure\WordPress\Component\PostHog\Application\Repository;

use WPML\Core\Component\PostHog\Application\Repository\PostHogStateRepositoryInterface;
use WPML\Core\Port\Persistence\OptionsInterface;

class PostHogStateRepository implements PostHogStateRepositoryInterface {

  /** @var OptionsInterface */
  private $options;

  const OPTION_NAME = 'wpml_posthog_enabled';


  public function __construct( OptionsInterface $options ) {
    $this->options = $options;
  }


  public function isEnabled(): bool {
    /** @var bool $isEnabled */
    $isEnabled = $this->options->get( self::OPTION_NAME );

    return $isEnabled;
  }


  public function setIsEnabled( bool $isEnabled ) {
    $this->options->save( self::OPTION_NAME, $isEnabled );
  }


}
