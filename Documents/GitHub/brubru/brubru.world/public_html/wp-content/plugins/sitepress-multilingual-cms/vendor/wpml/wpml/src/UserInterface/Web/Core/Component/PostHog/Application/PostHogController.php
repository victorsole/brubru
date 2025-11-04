<?php

namespace WPML\UserInterface\Web\Core\Component\PostHog\Application;

use WPML\Core\Component\PostHog\Application\Repository\PostHogStateRepositoryInterface;
use WPML\Core\Component\PostHog\Application\Service\Config\ConfigService;
use WPML\Core\SharedKernel\Component\Installer\Application\Query\WpmlActivePluginsQueryInterface;
use WPML\Core\SharedKernel\Component\Installer\Application\Query\WpmlSiteKeyQueryInterface;
use WPML\Core\SharedKernel\Component\PostHog\Application\Hook\FilterAllowedPagesInterface;
use WPML\Core\SharedKernel\Component\Site\Application\Query\SiteUrlQueryInterface;
use WPML\Core\SharedKernel\Component\User\Application\Query\UserQueryInterface;
use WPML\UserInterface\Web\Core\Port\Script\ScriptDataProviderInterface;
use WPML\UserInterface\Web\Core\Port\Script\ScriptPrerequisitesInterface;

class PostHogController implements
  ScriptPrerequisitesInterface,
  ScriptDataProviderInterface {

  const ALLOWED_PAGES = [
    'tm/menu/main.php',
    'sitepress-multilingual-cms/menu/languages.php',
    'sitepress-multilingual-cms/menu/theme-localization.php',
    'tm/menu/translations-queue.php',
    'tm/menu/settings',
    'sitepress-multilingual-cms/menu/menu-sync/menus-sync.php',
    'wpml-string-translation/menu/string-translation.php',
    'sitepress-multilingual-cms/menu/taxonomy-translation.php',
    'sitepress-multilingual-cms/menu/troubleshooting.php',
    'sitepress-multilingual-cms/menu/support.php',
    'wpml-media',
    'wpml-package-management',
    'sitepress-multilingual-cms/menu/debug-information.php',
    'wpml-tm-ate-log',
    'otgs-installer-support',
  ];

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

  /** @var FilterAllowedPagesInterface */
  private $filterAllowedPages;

  /** @var WpmlActivePluginsQueryInterface */
  private $wpmlActivePluginsQuery;


  public function __construct(
    ConfigService $configService,
    PostHogStateRepositoryInterface $posthogStateRepository,
    WpmlSiteKeyQueryInterface $siteKeyQuery,
    UserQueryInterface $userQuery,
    SiteUrlQueryInterface $siteUrlQuery,
    FilterAllowedPagesInterface $filterAllowedPages,
    WpmlActivePluginsQueryInterface $wpmlActivePluginsQuery
  ) {
    $this->configService          = $configService;
    $this->posthogStateRepository = $posthogStateRepository;
    $this->siteKeyQuery           = $siteKeyQuery;
    $this->userQuery              = $userQuery;
    $this->siteUrlQuery           = $siteUrlQuery;
    $this->filterAllowedPages     = $filterAllowedPages;
    $this->wpmlActivePluginsQuery = $wpmlActivePluginsQuery;
  }


  public function jsWindowKey(): string {
    return 'wpmlPostHog';
  }


  public function initialScriptData(): array {
    $config      = $this->configService->create();
    $currentUser = $this->userQuery->getCurrent();

    return [
      'apiKey'                  => $config->getApiKey(),
      'host'                    => $config->getHost(),
      'personProfiles'          => $config->getPersonProfiles(),
      'disableSurveys'          => $config->getDisableSurveys(),
      'autoCapture'             => $config->getAutoCapture(),
      'capturePageView'         => $config->getCapturePageView(),
      'capturePageLeave'        => $config->getCapturePageLeave(),
      'disableSessionRecording' => $config->getDisableSessionRecording(),
      'siteKey'                 => $this->siteKeyQuery->get() ?: '',
      'wpUserEmail'             => $currentUser ? $currentUser->getEmail() : null,
      'siteUrl'                 => $this->siteUrlQuery->get(),
      'wpmlActivePlugins'       => $this->wpmlActivePluginsQuery->getActivePlugins(),
    ];
  }


  public function scriptPrerequisitesMet(): bool {
    return $this->postHogAllowedForThisSite() &&
           array_key_exists( 'page', $_GET ) &&
           in_array( $_GET['page'], $this->filterAllowedPages->filter( self::ALLOWED_PAGES ) );
  }


  private function postHogAllowedForThisSite(): bool {
    return $this->posthogStateRepository->isEnabled();
  }


}
