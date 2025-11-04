<?php

namespace WPML\Legacy\Component\ATE\Application\Query;

use WPML\Core\SharedKernel\Component\ATE\Application\Query\SiteIDQueryInterface;

/**
 * The WPML_Site_ID::get_site_id() method will generate a site_id when it's missing,
 * I don't want that to happen in the get() method here, so I'm querying it from
 * the options table depending to constants defined in WPML_Site_ID class.
 */
class SiteIDQuery implements SiteIDQueryInterface {

  /** @var \WPML_Site_ID */
  private $wpmlSiteId;

  /** @var \WPML_TM_ATE */
  private $wpmlTmAte;


  public function __construct( \WPML_Site_ID $wpmlSiteId, \WPML_TM_ATE $wpmlTmAte ) {
    $this->wpmlSiteId = $wpmlSiteId;
    $this->wpmlTmAte  = $wpmlTmAte;
  }


  /**
   * @return string|null
   */
  public function get() {
    $optionKey = $this->wpmlSiteId::SITE_ID_KEY;
    $scope     = $this->wpmlTmAte::SITE_ID_SCOPE;

    /** @var string|null $result */
    $result = \get_option( $optionKey . ':' . $scope, null );
    return $result;
  }


}
