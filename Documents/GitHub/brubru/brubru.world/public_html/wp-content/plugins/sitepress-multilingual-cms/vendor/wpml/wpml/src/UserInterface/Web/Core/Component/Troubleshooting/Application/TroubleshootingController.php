<?php

namespace WPML\UserInterface\Web\Core\Component\Troubleshooting\Application;

use WPML\Core\Component\PostHog\Application\Repository\PostHogStateRepositoryInterface;
use WPML\Core\Component\PostHog\Application\Service\Config\ConfigService;
use WPML\Core\SharedKernel\Component\Installer\Application\Query\WpmlSiteKeyQueryInterface;
use WPML\Core\SharedKernel\Component\Site\Application\Query\SiteUrlQueryInterface;
use WPML\Core\SharedKernel\Component\User\Application\Query\UserQueryInterface;
use WPML\UserInterface\Web\Core\Port\Script\ScriptDataProviderInterface;
use WPML\UserInterface\Web\Core\Port\Script\ScriptPrerequisitesInterface;
use WPML\UserInterface\Web\Core\SharedKernel\Config\PageRequirementsInterface;

class TroubleshootingController implements
  ScriptDataProviderInterface,
  PageRequirementsInterface,
  ScriptPrerequisitesInterface {

  /** @var ConfigService */
  private $configService;

  /** @var PostHogStateRepositoryInterface */
  private $posthogStateRepository;

  /** @var WpmlSiteKeyQueryInterface */
  private $siteKeyQuery;

  /** @var UserQueryInterface */
  private $userQuery;

  /** @var SiteUrlQueryInterface */
  private $siteUrlQuery;


  public function __construct(
    ConfigService $configService,
    PostHogStateRepositoryInterface $posthogStateRepository,
    WpmlSiteKeyQueryInterface $siteKeyQuery,
    UserQueryInterface $userQuery,
    SiteUrlQueryInterface $siteUrlQuery
  ) {
    $this->configService          = $configService;
    $this->posthogStateRepository = $posthogStateRepository;
    $this->siteKeyQuery           = $siteKeyQuery;
    $this->userQuery              = $userQuery;
    $this->siteUrlQuery           = $siteUrlQuery;
  }


  /**
   * @return void
   */
  public static function render() {
    echo '<div id="wpml-troubleshooting-container-new"></div>';
  }


  public function jsWindowKey(): string {
    return 'troubleShootingScriptData';
  }


  public function initialScriptData(): array {
    return [
      'postHog' => $this->getPostHogScriptData(),
    ];
  }


  public function requirementsMet(): bool {
    return $this->isOnTroubleShootingPage();
  }


  public function scriptPrerequisitesMet(): bool {
    return $this->isOnTroubleShootingPage();
  }


  private function isOnTroubleShootingPage(): bool {
    return array_key_exists( 'page', $_GET ) &&
           $_GET['page'] === 'sitepress-multilingual-cms/menu/troubleshooting.php';
  }


  /**
   * @return array<string, mixed>
   */
  private function getPostHogScriptData(): array {
    $currentUser = $this->userQuery->getCurrent();
    $data        = [];

    $data['postHogRecordingEnabled'] = $this->posthogStateRepository->isEnabled();
    $data['siteKey']                 = $this->siteKeyQuery->get() ?: '';
    $data['wpUserEmail']             = $currentUser ? $currentUser->getEmail() : null;
    $data['siteUrl']                 = $this->siteUrlQuery->get();

    $config                                 = $this->configService->create();
    $data['postHogApiKey']                  = $config->getApiKey();
    $data['postHogHost']                    = $config->getHost();
    $data['postHogPersonProfiles']          = $config->getPersonProfiles();
    $data['postHogDisableSurveys']          = $config->getDisableSurveys();
    $data['postHogAutoCapture']             = $config->getAutoCapture();
    $data['postHogCapturePageView']         = $config->getCapturePageView();
    $data['postHogCapturePageLeave']        = $config->getCapturePageLeave();
    $data['postHogDisableSessionRecording'] = $config->getDisableSessionRecording();

    return $data;
  }


}
