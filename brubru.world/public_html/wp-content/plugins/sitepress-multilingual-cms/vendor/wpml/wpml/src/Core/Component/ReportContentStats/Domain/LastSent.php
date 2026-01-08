<?php

namespace WPML\Core\Component\ReportContentStats\Domain;

class LastSent {

  /** @var int|null */
  private $lastSent;


  /**
   * @param int|null $lastSent
   */
  public function __construct( $lastSent ) {
    $this->lastSent = $lastSent;
  }


  public function neverSent(): bool {
    return $this->lastSent === null;
  }


  public function lastSent30DaysAgoOrMore(): bool {
    return $this->lastSent !== null &&
           intval( ceil( ( time() - $this->lastSent ) / 86400 ) ) >= 30;
  }


}
