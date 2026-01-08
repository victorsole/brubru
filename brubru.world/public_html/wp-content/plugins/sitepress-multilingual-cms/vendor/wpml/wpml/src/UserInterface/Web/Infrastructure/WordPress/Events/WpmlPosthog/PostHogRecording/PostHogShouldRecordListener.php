<?php

namespace WPML\UserInterface\Web\Infrastructure\WordPress\Events\WpmlPosthog\PostHogRecording;

use WPML\Core\Component\PostHog\Application\Repository\PostHogStateRepositoryInterface;
use WPML\Core\Port\Event\EventListenerInterface;
use WPML\Core\SharedKernel\Component\Installer\Application\Query\WpmlSiteKeyQueryInterface;
use WPML\Core\SharedKernel\Component\WpmlOrgClient\Application\Service\PostHogRecording\PostHogRecordingService;

class PostHogShouldRecordListener implements EventListenerInterface {

  /** @var WpmlSiteKeyQueryInterface */
  private $siteKeyQuery;

  /** @var PostHogRecordingService */
  private $postHogRecordingService;

  /** @var PostHogStateRepositoryInterface */
  private $postHogStateRepository;


  public function __construct(
    WpmlSiteKeyQueryInterface $siteKeyQuery,
    PostHogRecordingService $postHogRecordingService,
    PostHogStateRepositoryInterface $postHogStateRepository
  ) {
    $this->siteKeyQuery            = $siteKeyQuery;
    $this->postHogRecordingService = $postHogRecordingService;
    $this->postHogStateRepository  = $postHogStateRepository;
  }


  /** @return void */
  public function check() {
    $siteKey = $this->siteKeyQuery->get();

    if ( ! $siteKey ) {
      return;
    }

    $result = $this->postHogRecordingService->run( $siteKey );
    $this->postHogStateRepository->setIsEnabled( $result['shouldRecord'] );
  }


}
