<?php

namespace WPML\Legacy\Component\ATE\Application\Query;

use WPML\Core\SharedKernel\Component\ATE\Application\Query\SiteSharedKeyQueryInterface;

class SiteSharedKeyQuery implements SiteSharedKeyQueryInterface {

  /** @var \WPML_TM_AMS_API */
  private $amsApi;


  public function __construct( \WPML_TM_AMS_API $amsApi ) {
    $this->amsApi = $amsApi;
  }


  /**
   * @return string|null
   */
  public function get() {
    $amsRegistrationData = $this->amsApi->get_registration_data();

    return array_key_exists( 'shared', $amsRegistrationData ) ?
      $amsRegistrationData['shared'] :
      null;
  }


}
