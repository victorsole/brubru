<?php

// Mapping of interfaces to implementations.

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus\MigrationStatusStorageInterface;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus\PreliminaryConditionQueryInterface;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\PreviousState\Factory as PreviousStateFactory;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\Compress\Factory as CompressFactory;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\CompressFix\Factory as CompressFixFactory;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\RemoveOld\Factory as RemoveOldFactory;
use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationPackageColumnInterface;
use WPML\Core\SharedKernel\Component\Server\Domain\CacheInterface;
use WPML\Core\SharedKernel\Component\Server\Domain\RestApiStatusInterface;
use WPML\Core\SharedKernel\Component\Server\Domain\ServerInfoInterface;
use WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus\MigrationStatusStorage;
use WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationStatus\PreliminaryConditionQuery;
use WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\PreviousState\Factory as PreviousStateFactoryImpl;
use WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\Compress\Factory as CompressFactoryImpl;
use WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\CompressFix\Factory as CompressFixFactoryImpl;
use WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\RemoveOld\Factory as RemoveOldFactoryImpl;
use WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationPackageColumn;
use WPML\Infrastructure\WordPress\SharedKernel\Server\Application\ServerInfo;
use WPML\Infrastructure\WordPress\SharedKernel\Server\Application\WordPressRestApiStatus;
use WPML\Infrastructure\WordPress\SharedKernel\Server\Application\WordPressTransientCache;
use WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\GetPopulatedItemSections\PopulatedItemSectionsFilterInterface;
use WPML\UserInterface\Web\Core\Component\Notices\PromoteUsingDashboard\Application\Repository\DashboardTranslationsRepositoryInterface;
use WPML\UserInterface\Web\Core\Component\Notices\PromoteUsingDashboard\Application\Repository\ManualTranslationsCountRepositoryInterface;
use WPML\UserInterface\Web\Infrastructure\WordPress\Component\NoticeStartUsingDashboard\Application\Repository\DashboardTranslationsRepository;
use WPML\UserInterface\Web\Infrastructure\WordPress\Component\NoticeStartUsingDashboard\Application\Repository\ManualTranslationsCountRepository;

return [

  /** CORE **/
  TranslationPackageColumnInterface::class  => TranslationPackageColumn::class,
  PreliminaryConditionQueryInterface::class => PreliminaryConditionQuery::class,

  // Factory interfaces for TranslationTablesOptimization
  PreviousStateFactory::class => PreviousStateFactoryImpl::class,
  CompressFactory::class      => CompressFactoryImpl::class,
  CompressFixFactory::class   => CompressFixFactoryImpl::class,
  RemoveOldFactory::class     => RemoveOldFactoryImpl::class,

  \WPML\Core\Port\Persistence\DatabaseSchemaInfoInterface::class =>
    \WPML\Infrastructure\WordPress\Port\Persistence\DatabaseSchemaInfo::class,

  \WPML\Core\Component\Translation\Domain\PreviousState\PreviousStateQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Domain\PreviousState\PreviousStateQuery::class,

  \WPML\Core\Component\Translation\Domain\PreviousState\PreviousStateRepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Domain\PreviousState\PreviousStateRepository::class,

  \WPML\Core\SharedKernel\Component\User\Application\Query\UserQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\User\Application\Query\UserQuery::class,

  \WPML\Core\Component\Post\Application\Query\SearchQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Item\Application\Query\SearchQuery::class,

  \WPML\Core\SharedKernel\Component\Post\Domain\Repository\RepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\SharedKernel\Post\Domain\Repository\Repository::class,

  \WPML\Core\Component\Post\Application\Query\HierarchicalPostQueryInterface::class =>
    \WPML\Legacy\Component\Post\Application\Query\HierarchicalPostQuery::class,

  \WPML\Core\Component\Post\Application\Query\PermalinkQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Item\Application\Query\PermalinkQuery::class,

  \WPML\Core\Component\Post\Application\Query\PublicationStatusQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Item\Application\Query\PublicationStatusQuery::class,

  \WPML\Core\Component\Post\Application\Query\TaxonomyQueryInterface::class =>
    \WPML\Legacy\Component\Post\Application\Query\TaxonomyQuery::class,

  \WPML\Core\Component\Translation\Application\Repository\TranslatorNoteRepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Application\Repository\PostTranslatorNoteRepository::class,

  \WPML\Core\Component\Translation\Application\Repository\TranslationRepositoryInterface::class =>
    \WPML\Legacy\Component\Translation\Application\Repository\TranslationRepository::class,

  \WPML\Core\SharedKernel\Component\Post\Application\Query\TranslatableTypesQueryInterface::class =>
    \WPML\Legacy\Component\Post\Application\Query\TranslatableTypesQuery::class,

  \WPML\Core\SharedKernel\Component\String\Application\Query\StringLanguageQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\String\Application\Query\StringLanguageQuery::class,

  \WPML\Core\Component\Translation\Application\String\Query\StringsFromBatchQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Application\String\Query\StringsFromBatchQuery::class,

  \WPML\Core\Component\Translation\Application\Query\TranslationBatchesQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Application\Query\TranslationBatchesQuery::class,

  \WPML\Core\Component\Translation\Application\Query\NeedsUpdateCreatedInCteQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Application\Query\NeedsUpdateCreatedInCteQuery::class,

  \WPML\Core\Component\Translation\Application\Query\TranslationStatusQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Application\Query\TranslationStatusQuery::class,

  \WPML\UserInterface\Web\Core\Component\Notices\WarningTranslationEdit\Application\TranslationEditorInterface::class =>
    \WPML\UserInterface\Web\Legacy\Component\Translation\TranslationEditor::class,

  \WPML\UserInterface\Web\Core\Port\Asset\AssetInterface::class =>
    \WPML\UserInterface\Web\Infrastructure\WordPress\Port\Asset\Asset::class,

  \WPML\Core\Component\Translation\Application\Query\ItemLanguageQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Application\Query\RegularItemsAndStringsLanguageQuery::class,

  // phpcs:ignore
  \WPML\Core\Component\Translation\Application\Query\TranslationQueryInterface::class => \WPML\Infrastructure\WordPress\Component\Translation\Application\Query\RegularItemsAndStringsTranslationQuery::class,

  \WPML\Core\Component\Translation\Application\Query\JobQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Application\Query\JobQuery::class,

  \WPML\Core\Component\ATE\Application\Query\AccountInterface::class =>
    \WPML\Legacy\Component\ATE\Application\Query\Account::class,

  \WPML\Core\Component\ATE\Application\Query\WebsiteContextQueryInterface::class =>
    \WPML\Legacy\Component\ATE\Application\Query\WebsiteContextQuery::class,

  \WPML\Core\Component\ATE\Application\Query\GlossaryInterface::class =>
    \WPML\Legacy\Component\ATE\Application\Query\Glossary::class,

  \WPML\Core\Port\Persistence\OptionsInterface::class =>
    \WPML\Infrastructure\WordPress\Port\Persistence\Options::class,

  \WPML\Core\Port\Persistence\QueryHandlerInterface::class =>
    \WPML\Infrastructure\WordPress\Port\Persistence\QueryHandler::class,

  \WPML\Core\Port\Persistence\QueryPrepareInterface::class =>
    \WPML\Infrastructure\WordPress\Port\Persistence\QueryPrepare::class,

  \WPML\Core\Port\Persistence\DatabaseAlterInterface::class =>
    \WPML\Infrastructure\WordPress\Port\Persistence\DatabaseAlter::class,

  \WPML\Core\Port\Persistence\DatabaseWriteInterface::class =>
    \WPML\Infrastructure\WordPress\Port\Persistence\DatabaseWrite::class,

  \WPML\Core\Component\Translation\Domain\Sender\TranslationSenderInterface::class =>
    \WPML\Legacy\Component\Translation\Sender\TranslationSender::class,

  \WPML\Core\Component\Translation\Domain\Sender\DuplicationSenderInterface::class =>
    \WPML\Legacy\Component\Translation\Sender\DuplicationSender::class,

  \WPML\Core\Component\Translation\Application\Query\PostTranslationQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Application\Query\PostTranslationQuery::class,

  \WPML\Core\SharedKernel\Component\Language\Application\Query\LanguagesQueryInterface::class =>
    \WPML\Legacy\Component\Language\Application\Query\LanguagesQuery::class,

  \WPML\Core\Component\Translation\Application\Service\TranslationService\BatchBuilder\BatchBuilderInterface::class =>
    \WPML\Core\Component\Translation\Application\Service\TranslationService\BatchBuilder\BatchBuilder::class,

  \WPML\Core\Component\Translation\Application\String\Repository\StringBatchRepositoryInterface::class =>
    \WPML\Legacy\Component\Translation\Application\String\Repository\StringBatchRepository::class,

  \WPML\Core\SharedKernel\Component\Translator\Domain\Query\TranslatorsQueryInterface::class =>
    \WPML\Legacy\Component\Translator\Domain\Query\TranslatorsQuery::class,

  \WPML\Core\SharedKernel\Component\Translator\Domain\Query\TranslatorLanguagePairsQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translator\Domain\Query\TranslatorLanguagePairsQuery::class,

  \WPML\Core\SharedKernel\Component\TranslationProxy\Domain\Query\RemoteTranslationServiceQueryInterface::class =>
    \WPML\Legacy\Component\TranslationProxy\Domain\Query\RemoteTranslationServiceQuery::class,

  \WPML\Core\Component\TranslationProxy\Application\Service\TranslationProxyServiceInterface::class =>
    \WPML\Legacy\Component\TranslationProxy\Application\Service\TranslationProxyService::class,

  \WPML\Core\Port\Event\DispatcherInterface::class =>
    \WPML\Infrastructure\WordPress\Port\Event\Dispatcher::class,

  \WPML\Core\Component\Translation\Domain\Links\CollectorInterface::class =>
    \WPML\Legacy\Component\Translation\Domain\Links\Collector::class,

  \WPML\Core\Component\Translation\Domain\Links\AdjustLinksInterface::class =>
    \WPML\Legacy\Component\Translation\Domain\Links\AdjustLinks::class,

  \WPML\Core\Component\Translation\Domain\Links\RepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Domain\Links\Repository::class,

  \WPML\Core\SharedKernel\Component\Post\Domain\PublicationStatusDefinitionsInterface::class        =>
    \WPML\Infrastructure\WordPress\SharedKernel\Post\Domain\PublicationStatusDefinitions::class,
  \WPML\Core\Component\TranslationProxy\Application\Service\LastPickedUpDateServiceInterface::class =>
    \WPML\Legacy\Component\TranslationProxy\Application\Service\LastPickedUpDateService::class,

  \WPML\Core\Component\TranslationProxy\Application\Query\RemoteJobsQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\TranslationProxy\Application\Query\RemoteJobsQuery::class,

  \WPML\Core\Component\Post\Domain\WordCount\StripCodeInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Item\Domain\WordCount\StripCode::class,

  \WPML\Core\SharedKernel\Component\String\Domain\Repository\RepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\String\Domain\Repository\Repository::class,

  \WPML\Core\SharedKernel\Component\StringPackage\Domain\Repository\RepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\StringPackage\Domain\Repository\Repository::class,

  \WPML\Core\Component\StringPackage\Application\Query\PackageDefinitionQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\StringPackage\Application\Query\PackageDefinitionQuery::class,

  \WPML\Core\SharedKernel\Component\Post\Domain\Repository\MetadataRepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\SharedKernel\Post\Domain\Repository\MetadataRepository::class,

  \WPML\Core\Component\Communication\Domain\DismissedNoticesStorageInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Communication\Domain\DismissedNoticesStorage::class,

  WPML\Core\Component\Post\Domain\WordCount\ItemContentCalculator\PostContentFilterInterface::class =>
    WPML\Infrastructure\WordPress\Component\Item\Domain\WordCount\ItemContentCalculator\PostContentFilter::class,

  \WPML\Core\Component\ATE\Application\Service\EnginesServiceInterface::class =>
    \WPML\Legacy\Component\ATE\Application\Service\EnginesService::class,

  \WPML\Core\Component\ReportContentStats\Domain\Query\OriginalContentStatsQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\ReportContentStats\Domain\Query\OriginalContentStatsQuery::class,

  \WPML\Core\Component\ReportContentStats\Domain\Query\TranslationCoverageStatsQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\ReportContentStats\Domain\Query\TranslationCoverageStatsQuery::class,

  \WPML\Core\Component\ReportContentStats\Domain\Repository\LastSentRepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\ReportContentStats\Domain\Repository\LastSentRepository::class,

  \WPML\Core\Component\ReportContentStats\Domain\Repository\PostTypesStatsRepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\ReportContentStats\Domain\Repository\PostTypesStatsRepository::class,

  \WPML\Core\Component\ReportContentStats\Domain\Repository\PostTypesToCalculateRepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\ReportContentStats\Domain\Repository\PostTypesToCalculateRepository::class,

  \WPML\Core\SharedKernel\Component\ATE\Application\Query\SiteIDQueryInterface::class =>
    \WPML\Legacy\Component\ATE\Application\Query\SiteIDQuery::class,

  \WPML\Core\SharedKernel\Component\ATE\Application\Query\SiteSharedKeyQueryInterface::class =>
    \WPML\Legacy\Component\ATE\Application\Query\SiteSharedKeyQuery::class,

  \WPML\Core\Component\ReportContentStats\Domain\ReportSenderInterface::class =>
    \WPML\Legacy\Component\ReportContentStats\Domain\ReportSender::class,

  \WPML\Core\Component\ReportContentStats\Application\Query\CanCollectStatsQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\ReportContentStats\Application\Query\CanCollectStatsQuery::class,

  \WPML\Core\Component\ReportContentStats\Application\Query\ContentStatsTranslatableTypesQueryInterface::class =>
    \WPML\Legacy\Component\ReportContentStats\Application\Query\ContentStatsTranslatableTypesQuery::class,

  \WPML\Core\SharedKernel\Component\Site\Application\Query\SiteUrlQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Site\Application\Query\SiteUrlQuery::class,

  \WPML\Core\SharedKernel\Component\Installer\Application\Query\WpmlSiteKeyQueryInterface::class =>
    \WPML\Legacy\SharedKernel\Installer\Application\Query\WpmlSiteKeyQuery::class,

  \WPML\Core\SharedKernel\Component\Installer\Application\Query\WpmlActivePluginsQueryInterface::class =>
    \WPML\Legacy\SharedKernel\Installer\Application\Query\WpmlActivePluginsQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\Post\Query\JobQueryInterface::class =>
    \WPML\Legacy\Component\WordsToTranslate\Domain\Post\JobQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\Post\Query\PostQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\Post\PostQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\Post\Query\TranslationQueryInterface::class =>
    \WPML\Legacy\Component\WordsToTranslate\Domain\Post\TranslationQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\Post\StoreRepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\Post\StoreRepository::class,

  \WPML\Core\Component\WordsToTranslate\Domain\Strings\Query\StringQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\Strings\StringQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\Strings\Query\TranslationQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\Strings\TranslationQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\StringBatch\Query\StringBatchQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\StringBatch\StringBatchQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query\JobQueryInterface::class =>
    \WPML\Legacy\Component\WordsToTranslate\Domain\StringPackage\JobQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query\StringPackageQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\StringPackage\StringPackageQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Query\TranslationQueryInterface::class =>
    \WPML\Legacy\Component\WordsToTranslate\Domain\StringPackage\TranslationQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\Job\Query\TranslationEngineQueryInterface::class =>
    \WPML\Legacy\Component\WordsToTranslate\Domain\Job\TranslationEngineQuery::class,

  \WPML\Core\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules\ShortcodeInterface::class =>
    \WPML\Infrastructure\WordPress\Component\WordsToTranslate\Domain\Calculator\PrepareContent\Rules\Shortcode::class,

  \WPML\Core\Component\PostHog\Application\Repository\PostHogStateRepositoryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\PostHog\Application\Repository\PostHogStateRepository::class,

  \WPML\Core\SharedKernel\Component\WpmlOrgClient\Domain\Api\Endpoints\PostHogRecordingInterface::class =>
    \WPML\Infrastructure\WordPress\SharedKernel\WpmlOrgClient\Domain\Api\Endpoints\PostHogRecording\PostHogRecording::class, // phpcs:ignore

  \WPML\Core\Component\PostHog\Application\Cookies\CookiesInterface::class =>
    \WPML\Infrastructure\WordPress\Component\PostHog\Application\Cookies\Cookies::class,

  \WPML\Core\Component\PostHog\Domain\Event\CaptureInterface::class =>
    \WPML\Infrastructure\WordPress\Component\PostHog\Domain\Event\Capture::class,

  \WPML\Core\SharedKernel\Component\PostHog\Application\Hook\FilterAllowedPagesInterface::class =>
    \WPML\UserInterface\Web\Infrastructure\WordPress\Component\PostHog\Application\Hook\FilterAllowedPages::class,

  /** USER INTERFACE **/
  \WPML\UserInterface\Web\Core\Component\Dashboard\Application\Hook\DashboardPublicationStatusFilterInterface::class =>
    \WPML\UserInterface\Web\Infrastructure\WordPress\Port\Hook\DashboardPublicationStatusFilter::class,

  \WPML\UserInterface\Web\Core\Component\Dashboard\Application\Hook\DashboardItemSectionsFilterInterface::class =>
    \WPML\UserInterface\Web\Infrastructure\WordPress\Port\Hook\DashboardItemSectionsFilter::class,

  WPML\UserInterface\Web\Core\Component\Dashboard\Application\Query\DashboardTranslatableTypesQueryInterface::class =>
    WPML\UserInterface\Web\Infrastructure\WordPress\Component\Dashboard\Query\DashboardTranslatableTypesQuery::class,

  WPML\UserInterface\Web\Core\Component\Dashboard\Application\Hook\DashboardTranslatablePostTypesFilterInterface::class
  => \WPML\UserInterface\Web\Infrastructure\WordPress\Port\Hook\DashboardTranslatablePostTypesFilter::class,

  WPML\UserInterface\Web\Core\Component\Dashboard\Application\DashboardTabsInterface::class =>
    WPML\UserInterface\Web\Legacy\Component\Dashboard\DashboardTabs::class,

  \WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\GetPosts\GetPostControllerInterface::class =>
    \WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\GetPosts\WordCountDecoratorController::class,

  WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\GetPosts\PostsFilterInterface::class =>
    WPML\UserInterface\Web\Infrastructure\WordPress\Port\Hook\PostsFilter::class,

  WPML\Core\Component\Post\Application\Query\SearchPopulatedTypesQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Item\Application\Query\SearchPopulatedTypesQuery::class,

  PopulatedItemSectionsFilterInterface::class =>
    \WPML\UserInterface\Web\Infrastructure\WordPress\Port\Hook\PopulatedItemSectionsFilter::class,

  DashboardTranslationsRepositoryInterface::class => DashboardTranslationsRepository::class,

  ManualTranslationsCountRepositoryInterface::class => ManualTranslationsCountRepository::class,

  MigrationStatusStorageInterface::class => MigrationStatusStorage::class,

  \WPML\Core\Component\Translation\Domain\PreviousState\DataCompressInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Domain\PreviousState\OnlyDataSerialization::class,

  RestApiStatusInterface::class => WordPressRestApiStatus::class,

  ServerInfoInterface::class => ServerInfo::class,

  \WPML\Core\Component\Translation\Application\Query\HasPostsUsingNativeEditorQueryInterface::class =>
    \WPML\Infrastructure\WordPress\Component\Translation\Application\Query\HasPostsUsingNativeEditorQuery::class,

  CacheInterface::class => WordPressTransientCache::class,

];
