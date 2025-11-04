<?php

// Mapping of class definitions.
// Use this if a class needs a specific implementation other than the default
// interface mapping (of config-interface-mappings.php).

// FORMAT: className => [ 'argument1Name' => className1, 'argument2Name' => className2, ... ]
// You only need to specify the arguments that need a specific implementation.

// Example:
// MyClass::__construct(Interface1 $arg1, Interface2 $arg2)
// I only want to specify the implementation of $arg2 so the mapping would be:
// MyClass::class => ['arg2' => SpecificImplementation::class]

use WPML\Core\Component\MinimumRequirements\Application\Service\RequirementsService;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\DatabaseVersionRequirement;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\EvalFunctionRequirement;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\LibXmlVersionRequirement;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\MbstringExtensionRequirement;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\MemoryLimitRequirement;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\PHPVersionRequirement;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\RestEnabledRequirement;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\SimpleXMLExtensionRequirement;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\StackSizeRequirement;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\WordPressVersionRequirement;
use WPML\Core\Component\Translation\Application\Repository\SettingsRepository;
use WPML\Core\Component\Translation\Application\Service\TranslationService;
use WPML\Core\Component\Translation\Application\Service\TranslatorNoteService;
use WPML\Core\Component\Translation\Application\String\StringBatchBuilder;
use WPML\Core\Component\Translation\Domain\CompletedTranslationDetector;
use WPML\Core\Component\Translation\Domain\TranslationBatch\Validator\CompletedTranslationValidator;
use WPML\Core\Component\Translation\Domain\TranslationBatch\Validator\CompositeValidator;
use WPML\Core\Component\Translation\Domain\TranslationBatch\Validator\ElementTargetLanguageValidator;
use WPML\Core\Component\Translation\Domain\TranslationBatch\Validator\EmptyMethodsValidator;
use WPML\Core\Component\Translation\Domain\TranslationBatch\Validator\ValidatorInterface;
use WPML\Core\SharedKernel\Component\Language\Application\Query\LanguagesQueryInterface;
use WPML\Core\SharedKernel\Component\Server\Domain\CacheInterface;
use WPML\Core\SharedKernel\Component\User\Application\Query\UserQueryInterface;
use WPML\DicInterface;
use WPML\Infrastructure\WordPress\Component\Item\Application\Query\SearchQuery\QueryBuilder\ManyLanguagesStrategy\QueryBuilderFactory as ManyTargetLanguagesFactory;
use WPML\Infrastructure\WordPress\Component\Item\Application\Query\SearchQuery\QueryBuilder\ManyLanguagesStrategy\SearchPopulatedTypesQueryBuilder as ManyLanguagesStrategySearchPopulatedTypesQueryBuilder;
use WPML\Infrastructure\WordPress\Component\Item\Application\Query\SearchQuery\QueryBuilder\ManyLanguagesStrategy\SearchQueryBuilder as ManyLanguagesStrategySearchQueryBuilder;
use WPML\Infrastructure\WordPress\Component\Item\Application\Query\SearchQuery\QueryBuilder\MultiJoinStrategy\QueryBuilderFactory as MultiJoinFactory;
use WPML\Infrastructure\WordPress\Component\Item\Application\Query\SearchQuery\QueryBuilder\MultiJoinStrategy\SearchPopulatedTypesQueryBuilder as MultiJoinStrategySearchPopulatedTypesQueryBuilder;
use WPML\Infrastructure\WordPress\Component\Item\Application\Query\SearchQuery\QueryBuilder\MultiJoinStrategy\SearchQueryBuilder as MultiJoinStrategySearchQueryBuilder;
use WPML\Infrastructure\WordPress\Component\Item\Application\Query\SearchQuery\QueryBuilder\QueryBuilderResolver;
use WPML\Infrastructure\WordPress\Component\Item\Application\Query\UntranslatedTypesCountQuery as PostUntranslatedTypesCountQuery;
use WPML\Infrastructure\WordPress\Component\String\Application\Query\UntranslatedTypesCountQuery as StringUntranslatedTypesCountQuery;
use WPML\Infrastructure\WordPress\Component\StringPackage\Application\Query\UntranslatedTypesCountQuery as PackageUntranslatedTypesCountQuery;
use WPML\Infrastructure\WordPress\Component\Translation\Application\Repository\StringPackageTranslatorNoteRepository;
use WPML\Legacy\Component\Language\Application\Query\AutomaticTranslationsSupportInfoDecoratorForLanguagesQuery;
use WPML\Legacy\Component\Language\Application\Query\LanguagesQuery;
use WPML\Legacy\Component\Translation\Domain\TranslationBatch\Validator\Base64Validator;
use WPML\Legacy\Component\Translation\Sender\ErrorMapper\ErrorMapper;
use WPML\Legacy\Component\Translation\Sender\ErrorMapper\LegacyAteJobCreationError;
use WPML\Legacy\Component\Translation\Sender\ErrorMapper\UnsupportedLanguagesInTranslationService;
use WPML\Legacy\Port\Plugin;
use WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\GetPosts\GetPostsController;
use WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\GetPosts\WordCountDecoratorController;
use WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\GetUntranslatedTypesCount\GetUntranslatedTypesCountController;
use WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\TranslateEverything\EnableController;
use WPML\UserInterface\Web\Core\Component\Notices\PromoteUsingDashboard\Application\Repository\ManualTranslationsCountRepositoryInterface;
use WPML\UserInterface\Web\Core\Component\Notices\PromoteUsingDashboard\Application\Service\ManualTranslationsCountService;
use WPML\UserInterface\Web\Core\Component\Preferences\Application\LanguagePreferencesLoader;
use WPML\UserInterface\Web\Infrastructure\WordPress\CompositionRoot\Config\Api;
use WPML\UserInterface\Web\Infrastructure\WordPress\CompositionRoot\Config\ExistingPage\PostEditPage;
use WPML\UserInterface\Web\Infrastructure\WordPress\CompositionRoot\Config\ExistingPage\PostListingPage;

return [
  \WPML\UserInterface\Web\Infrastructure\CompositionRoot\Config\ContentStats\Controller::class =>
    [ 'api' => Api::class, ],
  TranslationService::class                                                                    =>
    [ 'batchBuilder' => StringBatchBuilder::class ],
  TranslatorNoteService::class                                                                 =>
    [
      'stringPackageTranslatorNoteRepo' =>
      // phpcs:ignore Glingener.File.LineLength.LineTooLong
        StringPackageTranslatorNoteRepository::class
    ],
  WordCountDecoratorController::class                                                          =>
    [
      'innerController' =>
        GetPostsController::class
    ],

  GetUntranslatedTypesCountController::class =>
    function ( DicInterface $dic ) {
      $queries = [ $dic->make( PostUntranslatedTypesCountQuery::class ) ];

      if ( defined( 'WPML_ST_VERSION' ) ) {
        $queries[] = $dic->make( PackageUntranslatedTypesCountQuery::class );
        $queries[] = $dic->make( StringUntranslatedTypesCountQuery::class );
      }

      return new GetUntranslatedTypesCountController(
        $queries,
        $dic->make( SettingsRepository::class )
      );
    },

  AutomaticTranslationsSupportInfoDecoratorForLanguagesQuery::class =>
    [ 'languagesQuery' => LanguagesQuery::class ],

  EnableController::class               =>
    [
      'languagesQuery' => AutomaticTranslationsSupportInfoDecoratorForLanguagesQuery::class
    ],
  LanguagePreferencesLoader::class      =>
    [
      'languagesQuery' => AutomaticTranslationsSupportInfoDecoratorForLanguagesQuery::class,
      'pluginInterface'=> Plugin::class,
    ],
  ValidatorInterface::class             =>
    function ( DicInterface $dic ) {
      return new CompositeValidator(
        [
          new ElementTargetLanguageValidator(),
          new CompletedTranslationValidator( $dic->make( CompletedTranslationDetector::class ) ),
          new Base64Validator()
        ],
        new EmptyMethodsValidator()
      );
    },
  ErrorMapper::class                    =>
    function ( DicInterface $dic ) {
      return new ErrorMapper(
        [
          $dic->make( UnsupportedLanguagesInTranslationService::class ),
          $dic->make( LegacyAteJobCreationError::class )
        ]
      );
    },
  QueryBuilderResolver::class           =>
    function ( DicInterface $dic ) {
      return new QueryBuilderResolver(
        $dic->make( LanguagesQueryInterface::class ),
        new ManyTargetLanguagesFactory(
          $dic->make( ManyLanguagesStrategySearchQueryBuilder::class ),
          $dic->make( ManyLanguagesStrategySearchPopulatedTypesQueryBuilder::class )
        ),
        new MultiJoinFactory(
          $dic->make( MultiJoinStrategySearchQueryBuilder::class ),
          $dic->make( MultiJoinStrategySearchPopulatedTypesQueryBuilder::class )
        )
      );
    },
  ManualTranslationsCountService::class =>
    function ( DicInterface $dic ) {
      return new ManualTranslationsCountService(
        $dic->make( ManualTranslationsCountRepositoryInterface::class ),
        $dic->make( UserQueryInterface::class ),
        [
          $dic->make( PostListingPage::class ),
          $dic->make( PostEditPage::class ),
        ]
      );
    },
  RequirementsService::class            => function (
    DicInterface $dic
  ) {
    $requirements = [
      $dic->make( MemoryLimitRequirement::class ),
      $dic->make( PHPVersionRequirement::class ),
      $dic->make( DatabaseVersionRequirement::class ),
      $dic->make( RestEnabledRequirement::class ),
      $dic->make( SimpleXMLExtensionRequirement::class ),
      $dic->make( WordPressVersionRequirement::class ),
      $dic->make( EvalFunctionRequirement::class ),
      $dic->make( LibXmlVersionRequirement::class ),
      $dic->make( MbstringExtensionRequirement::class ),
      $dic->make( StackSizeRequirement::class ),

    ];

    return new RequirementsService(
      $requirements,
      $dic->make( CacheInterface::class )
    );
  },

  \WPML\Core\Component\WordsToTranslate\Domain\Post\Provider::class =>
    [
      // Comment out the following line to completely ignore terms in WTT.
      'postTermsLoader' => WPML\Core\Component\WordsToTranslate\Domain\Post\PostTermsLoader::class,
    ],

    \WPML\Core\Component\WordsToTranslate\Domain\Provider::class =>
    function ( DicInterface $dic ) {
      return new \WPML\Core\Component\WordsToTranslate\Domain\Provider(
        [
         $dic->make( \WPML\Core\Component\WordsToTranslate\Domain\Post\Provider::class ),
         $dic->make( \WPML\Core\Component\WordsToTranslate\Domain\Strings\Provider::class ),
         $dic->make( \WPML\Core\Component\WordsToTranslate\Domain\StringBatch\Provider::class ),
         $dic->make( \WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Provider::class ),
        ]
      );
    },

  \WPML\Core\Component\WordsToTranslate\Domain\Job\Provider::class =>
    function ( DicInterface $dic ) {
      return new \WPML\Core\Component\WordsToTranslate\Domain\Job\Provider(
        new \WPML\Legacy\Component\WordsToTranslate\Domain\Job\JobQuery(),
        new \WPML\Legacy\Component\WordsToTranslate\Domain\Job\TranslationEngineQuery(),
        [
         $dic->make( \WPML\Core\Component\WordsToTranslate\Domain\Post\Provider::class ),
         $dic->make( \WPML\Core\Component\WordsToTranslate\Domain\Strings\Provider::class ),
         $dic->make( \WPML\Core\Component\WordsToTranslate\Domain\StringBatch\Provider::class ),
         $dic->make( \WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Provider::class ),
        ]
      );
    },
];
