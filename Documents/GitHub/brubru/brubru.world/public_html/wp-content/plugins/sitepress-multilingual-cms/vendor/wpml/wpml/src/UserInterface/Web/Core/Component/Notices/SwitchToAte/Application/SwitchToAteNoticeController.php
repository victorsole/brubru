<?php

namespace WPML\UserInterface\Web\Core\Component\Notices\SwitchToAte\Application;

use WPML\Core\Component\Communication\Application\Query\DismissedNoticesQuery;
use WPML\Core\Component\Translation\Application\Repository\SettingsRepository;
use WPML\Core\SharedKernel\Component\User\Application\Query\UserQueryInterface;
use WPML\UserInterface\Web\Core\SharedKernel\Config\NoticeRenderInterface;
use WPML\UserInterface\Web\Core\SharedKernel\Config\NoticeRequirementsInterface;

class SwitchToAteNoticeController implements NoticeRenderInterface, NoticeRequirementsInterface {

  /** @var DismissedNoticesQuery */
  private $dismissedNoticesQuery;

  /** @var UserQueryInterface */
  private $userQuery;

  /** @var SettingsRepository */
  private $settingsRepository;

  /** @var string */
  private $noticeId;


  public function __construct(
    DismissedNoticesQuery $dismissedNoticesQuery,
    UserQueryInterface $userQuery,
    SettingsRepository $settingsRepository
  ) {
    $this->dismissedNoticesQuery = $dismissedNoticesQuery;
    $this->userQuery = $userQuery;
    $this->settingsRepository = $settingsRepository;
    $this->noticeId = 'switch-to-ate-notice';
  }


  /**
   * @return void
   */
  public function render() {
    echo <<<HTML
      <div class="wpml-notice-ate-banner-wrapper" id="wpml-switch-to-ate-notice"></div>
      <script>
        document.addEventListener('DOMContentLoaded', function() {
          const tmDashboardWrapper = document.querySelector('.icl_tm_wrap');
          const noticeRoot = document.getElementById('wpml-switch-to-ate-notice');
          if ( tmDashboardWrapper ) {
            tmDashboardWrapper.prepend(noticeRoot);
            noticeRoot.style.display = 'block';
          }
        } );
      </script>
HTML;
  }


  public function requirementsMet() : bool {
    return $this->isAteDisabled() && $this->noticeIsVisibleToCurrentUser();
  }


  private function noticeIsVisibleToCurrentUser() : bool {
    $user = $this->userQuery->getCurrent();

    if ( ! $user ) {
      return false;
    }

    return empty( $this->dismissedNoticesQuery->getDismissedByUser( $user->getId(), [ $this->noticeId ] ) );
  }


  private function isAteDisabled() : bool {
    $translationEditor = $this->settingsRepository->getSettings()->getTranslationEditor();

    return $translationEditor && $translationEditor->getValue() !== 'ATE';
  }


}
