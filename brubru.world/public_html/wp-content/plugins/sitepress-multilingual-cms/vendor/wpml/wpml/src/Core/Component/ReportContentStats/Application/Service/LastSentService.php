<?php

namespace WPML\Core\Component\ReportContentStats\Application\Service;

use WPML\Core\Component\ReportContentStats\Domain\LastSent;
use WPML\Core\Component\ReportContentStats\Domain\Repository\LastSentRepositoryInterface;

class LastSentService {

  /** @var LastSentRepositoryInterface */
  private $lastSentRepository;


  public function __construct(
    LastSentRepositoryInterface $lastSentRepository
  ) {
    $this->lastSentRepository = $lastSentRepository;
  }


  /**
   * @return int|null
   */
  public function get() {
    return $this->lastSentRepository->get();
  }


  public function neverSentOrSent30DaysAgo(): bool {
    $lastSentDomain = ( new LastSent( $this->get() ) );

    return $lastSentDomain->neverSent() || $lastSentDomain->lastSent30DaysAgoOrMore();
  }


  /**
   * @param int $lastSent
   *
   * @return void
   */
  public function update( int $lastSent ) {
    $this->lastSentRepository->update( $lastSent );
  }


}
