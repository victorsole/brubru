# WPML Functional Programming Library

## Table of Contents

* [Cast](#Cast)
    * [__call](#__call)
    * [__callStatic](#__callstatic)
    * [hasMacro](#hasmacro)
    * [init](#init)
    * [macro](#macro)
    * [toBool](#tobool)
    * [toInt](#toint)
    * [toStr](#tostr)
    * [toArr](#toarr)
* [Either](#Either)
    * [of](#of)
    * [left](#left)
    * [right](#right)
    * [fromNullable](#fromnullable)
    * [fromBool](#frombool)
    * [tryCatch](#trycatch)
    * [getOrElse](#getorelse)
* [Fns](#Fns)
    * [__call](#__call)
    * [__callStatic](#__callstatic)
    * [hasMacro](#hasmacro)
    * [init](#init)
    * [macro](#macro)
    * [maybeToEither](#maybetoeither)
    * [noop](#noop)
    * [always](#always)
    * [converge](#converge)
    * [map](#map)
    * [each](#each)
    * [identity](#identity)
    * [tap](#tap)
    * [reduce](#reduce)
    * [reduceRight](#reduceright)
    * [filter](#filter)
    * [reject](#reject)
    * [value](#value)
    * [constructN](#constructn)
    * [ascend](#ascend)
    * [descend](#descend)
    * [useWith](#usewith)
    * [nthArg](#ntharg)
    * [either](#either)
    * [maybe](#maybe)
    * [isRight](#isright)
    * [isLeft](#isleft)
    * [isJust](#isjust)
    * [isNothing](#isnothing)
    * [T](#t)
    * [F](#f)
    * [safe](#safe)
    * [make](#make)
    * [makeN](#maken)
    * [unary](#unary)
    * [memorizeWith](#memorizewith)
    * [memorize](#memorize)
    * [once](#once)
    * [withNamedLock](#withnamedlock)
    * [withoutRecursion](#withoutrecursion)
    * [liftA2](#lifta2)
    * [liftA3](#lifta3)
    * [liftN](#liftn)
    * [until](#until)
* [Json](#Json)
    * [__call](#__call)
    * [__callStatic](#__callstatic)
    * [hasMacro](#hasmacro)
    * [init](#init)
    * [macro](#macro)
    * [toArray](#toarray)
    * [toCollection](#tocollection)
* [Lens](#Lens)
    * [__call](#__call)
    * [__callStatic](#__callstatic)
    * [hasMacro](#hasmacro)
    * [init](#init)
    * [macro](#macro)
    * [iso](#iso)
    * [isoIdentity](#isoidentity)
    * [isoUnserialized](#isounserialized)
    * [isoJsonDecoded](#isojsondecoded)
    * [isoUrlDecoded](#isourldecoded)
    * [isoBase64Decoded](#isobase64decoded)
    * [isoParsedUrl](#isoparsedurl)
    * [isoParsedQuery](#isoparsedquery)
* [Logic](#Logic)
    * [__call](#__call)
    * [__callStatic](#__callstatic)
    * [hasMacro](#hasmacro)
    * [init](#init)
    * [macro](#macro)
    * [not](#not)
    * [isNotNull](#isnotnull)
    * [ifElse](#ifelse)
    * [when](#when)
    * [unless](#unless)
    * [cond](#cond)
    * [both](#both)
    * [allPass](#allpass)
    * [anyPass](#anypass)
    * [complement](#complement)
    * [defaultTo](#defaultto)
    * [either](#either)
    * [until](#until)
    * [propSatisfies](#propsatisfies)
    * [isArray](#isarray)
    * [isMappable](#ismappable)
    * [isEmpty](#isempty)
    * [isNotEmpty](#isnotempty)
    * [firstSatisfying](#firstsatisfying)
    * [isTruthy](#istruthy)
* [Lst](#Lst)
    * [__call](#__call)
    * [__callStatic](#__callstatic)
    * [diff](#diff)
    * [hasMacro](#hasmacro)
    * [init](#init)
    * [keyBy](#keyby)
    * [keyWith](#keywith)
    * [macro](#macro)
    * [repeat](#repeat)
    * [sum](#sum)
    * [append](#append)
    * [fromPairs](#frompairs)
    * [toObj](#toobj)
    * [pluck](#pluck)
    * [partition](#partition)
    * [sort](#sort)
    * [unfold](#unfold)
    * [zip](#zip)
    * [zipObj](#zipobj)
    * [zipWith](#zipwith)
    * [join](#join)
    * [joinWithCommasAndAnd](#joinwithcommasandand)
    * [concat](#concat)
    * [find](#find)
    * [flattenToDepth](#flattentodepth)
    * [flatten](#flatten)
    * [includes](#includes)
    * [includesAll](#includesall)
    * [nth](#nth)
    * [first](#first)
    * [last](#last)
    * [length](#length)
    * [take](#take)
    * [takeLast](#takelast)
    * [slice](#slice)
    * [drop](#drop)
    * [dropLast](#droplast)
    * [makePair](#makepair)
    * [make](#make)
    * [insert](#insert)
    * [range](#range)
    * [xprod](#xprod)
    * [prepend](#prepend)
    * [reverse](#reverse)
* [Math](#Math)
    * [__call](#__call)
    * [__callStatic](#__callstatic)
    * [hasMacro](#hasmacro)
    * [init](#init)
    * [macro](#macro)
    * [multiply](#multiply)
    * [divide](#divide)
    * [add](#add)
    * [product](#product)
* [Maybe](#Maybe)
    * [fromNullable](#fromnullable)
    * [safe](#safe)
    * [safeAfter](#safeafter)
    * [safeBefore](#safebefore)
    * [just](#just)
    * [of](#of)
* [Obj](#Obj)
    * [__call](#__call)
    * [__callStatic](#__callstatic)
    * [hasMacro](#hasmacro)
    * [init](#init)
    * [macro](#macro)
    * [merge](#merge)
    * [without](#without)
    * [prop](#prop)
    * [propOr](#propor)
    * [props](#props)
    * [addProp](#addprop)
    * [removeProp](#removeprop)
    * [renameProp](#renameprop)
    * [path](#path)
    * [pathOr](#pathor)
    * [assoc](#assoc)
    * [assocPath](#assocpath)
    * [lens](#lens)
    * [lensProp](#lensprop)
    * [lensPath](#lenspath)
    * [lensMapped](#lensmapped)
    * [lensMappedProp](#lensmappedprop)
    * [view](#view)
    * [set](#set)
    * [over](#over)
    * [pick](#pick)
    * [pickAll](#pickall)
    * [pickBy](#pickby)
    * [pickByKey](#pickbykey)
    * [project](#project)
    * [where](#where)
    * [has](#has)
    * [hasPath](#haspath)
    * [evolve](#evolve)
    * [objOf](#objof)
    * [keys](#keys)
    * [values](#values)
    * [replaceRecursive](#replacerecursive)
    * [toArray](#toarray)
* [Relation](#Relation)
    * [__call](#__call)
    * [__callStatic](#__callstatic)
    * [hasMacro](#hasmacro)
    * [init](#init)
    * [macro](#macro)
    * [equals](#equals)
    * [lt](#lt)
    * [lte](#lte)
    * [gt](#gt)
    * [gte](#gte)
    * [propEq](#propeq)
    * [sortWith](#sortwith)
* [Str](#Str)
    * [__call](#__call)
    * [__callStatic](#__callstatic)
    * [hasMacro](#hasmacro)
    * [init](#init)
    * [macro](#macro)
    * [truncate_bytes](#truncate_bytes)
    * [tail](#tail)
    * [split](#split)
    * [parse](#parse)
    * [includes](#includes)
    * [trim](#trim)
    * [trimPrefix](#trimprefix)
    * [concat](#concat)
    * [sub](#sub)
    * [startsWith](#startswith)
    * [endsWith](#endswith)
    * [pos](#pos)
    * [len](#len)
    * [replace](#replace)
    * [pregReplace](#pregreplace)
    * [match](#match)
    * [matchAll](#matchall)
    * [wrap](#wrap)
    * [toUpper](#toupper)
    * [toLower](#tolower)

* Cast
### __call




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### __callStatic




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### hasMacro




Checks if macro is registered. 

 

**Parameters**

* `(string) $name`

**Return Values**

`bool`






### init



 init (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### macro




Register a custom macro. 

 

**Parameters**

* `(string) $name`
* `(callable) $macro`

**Return Values**

`void`






### toBool

**Signature:** `toBool(mixed ...$v)`



Curried :: mixed->bool

### toInt

**Signature:** `toInt(mixed ...$v)`



Curried :: mixed->int

### toStr

**Signature:** `toStr(mixed ...$v)`



Curried :: mixed->string

### toArr

**Signature:** `toArr(mixed ...$v)`



Curried :: mixed->array


* Either
### of





Curried :: a → Right a
 *


### left





Curried :: a → Left a
 *


### right





Curried :: a → Right a
 *


### fromNullable





Curried :: a → Either a
 *


### fromBool





Curried :: a → Either a
 *


### tryCatch





Curried :: a → Either a
 *


### getOrElse








* Fns
### __call




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### __callStatic




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### hasMacro




Checks if macro is registered. 

 

**Parameters**

* `(string) $name`

**Return Values**

`bool`






### init



 init (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### macro




Register a custom macro. 

 

**Parameters**

* `(string) $name`
* `(callable) $macro`

**Return Values**

`void`






### maybeToEither




Curried function that transforms a Maybe into an Either. 

 

**Parameters**

* `(mixed|null) $or`
* `(\Maybe|null) $maybe`

**Return Values**

`callable|\Either`






### noop



 noop (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### always

**Signature:** `always(...$a)`

Curried :: a → ( → a )
 Returns a function that always returns the given value.
 ```php
 $t = Fns::always( 'Tee' );
 $t(); //=> 'Tee'
 ```
 *

### converge

**Signature:** `converge(...$convergingFn, ...$branchingFns)`



Curried :: ( ( x1, x2, … ) → z ) → [( ( a, b, … ) → x1 ), ( ( a, b, … ) → x2 ), …] → ( a → b → … → z )
 Accepts a converging function and a list of branching functions and returns a new function. The arity of the new function is the same as the arity of the longest branching function. When invoked, this new function is applied to some arguments, and each branching function is applied to those same arguments. The results of each branching function are passed as arguments to the converging function to produce the return value.
 ```php
 $divide = curryN( 2, function ( $num, $dom ) { return $num / $dom; } );
 $sum    = function ( Collection $collection ) { return $collection->sum(); };
 $length = function ( Collection $collection ) { return $collection->count(); };
 $average = Fns::converge( $divide, [ $sum, $length ] );
 $this->assertEquals( 4, $average( wpml_collect( [ 1, 2, 3, 4, 5, 6, 7 ] ) ) );
 ```
 *

### map

**Signature:** `map(...$fn, ...$target)`



Curried :: ( a→b )→f a→f b
 Takes a function and a *functor*, applies the function to each of the functor's values, and returns a functor of the same shape.
 And array is considered a *functorDispatches to the *mapmethod of the second argument, if present
 *

### each

**Signature:** `each(...$fn, ...$target)`



Curried :: ( a→b )→f a→f b

### identity

**Signature:** `identity(mixed ...$data)`



Curried :: a->a

### tap

**Signature:** `tap(callable  ...$fn, mixed ...$data)`



Curried :: fn->data->data

### reduce

**Signature:** `reduce(...$fn, ...$initial, ...$target)`



Curried :: ( ( a, b ) → a ) → a → [b] → a

### reduceRight

**Signature:** `reduceRight(...$fn, ...$initial, ...$target)`



Curried :: ( ( a, b ) → a ) → a → [b] → a
 Takes a function, an initial value and an array and returns the result.
 The function receives two values, the accumulator and the current value, and should return a result.
 The array values are passed to the function in the reverse order.
 ```php
 $numbers = [ 1, 2, 3, 4, 5, 8, 19 ];
 $append = function( $acc, $val ) {
 $acc[] = $val;
 return $acc;
 };
 $reducer = Fns::reduceRight( $append, [] );
 $result = $reducer( $numbers ); // [ 19, 8, 5, 4, 3, 2, 1 ]
 // Works on collections too.
 $result = $reducer( wpml_collect( $numbers ) ); // [ 19, 8, 5, 4, 3, 2, 1 ]
 ```
 *

### filter

**Signature:** `filter(...$predicate, ...$target)`



Curried :: ( a → bool ) → [a] → [a]

### reject

**Signature:** `reject(...$predicate, ...$target)`



Curried :: ( a → bool ) → [a] → [a]

### value

**Signature:** `value(mixed ...$data)`



Curried :: a|( *→a ) → a

### constructN

**Signature:** `constructN(...$argCount, ...$className)`



Curried :: int → string → object

### ascend

**Signature:** `ascend(...$fn, ...$a, ...$b)`



Curried :: ( a → b ) → a → a → int

### descend

**Signature:** `descend(...$fn, ...$a, ...$b)`



Curried :: ( a → b ) → a → a → int

### useWith

**Signature:** `useWith(...$fn, ...$transformations)`



Curried :: ( ( x1, x2, … ) → z ) → [( a → x1 ), ( b → x2 ), …] → ( a → b → … → z )

### nthArg

**Signature:** `nthArg(...$n)`



Curried :: int → *… → *

### either

**Signature:** `either(...$f, ...$g, ...$e)`



Curried :: ( a → b ) → ( b → c ) → Either a b → c

### maybe

**Signature:** `maybe(...$v, ...$f, ...$m)`



Curried :: b → ( a → b ) → Maybe a → b

### isRight

**Signature:** `isRight(...$e)`



Curried :: e → bool

### isLeft

**Signature:** `isLeft(...$e)`



Curried :: e → bool

### isJust

**Signature:** `isJust(...$m)`



Curried :: e → bool

### isNothing

**Signature:** `isNothing(...$m)`



Curried :: e → bool

### T

**Signature:** `T(...$_)`



Curried :: _ → bool

### F

**Signature:** `F(...$_)`



Curried :: _ → bool

### safe

**Signature:** `safe(...$fn)`



Curried :: ( a → b ) → ( a → Maybe b )

### make

**Signature:** `make(...$className)`



Curried :: string → object

### makeN

**Signature:** `makeN(...$argCount, ...$className)`



Curried :: int → string → object

### unary

**Signature:** `unary(...$fn)`



Curried :: ( → b ) → ( a → b )

### memorizeWith

**Signature:** `memorizeWith(...$cacheKeyFn, ...$fn)`



Curried :: ( *… → String ) → ( *… → a ) → ( *… → a )

### memorize

**Signature:** `memorize(...$fn)`



Curried :: ( *… → a ) → ( *… → a )

### once

**Signature:** `once(...$fn)`



Curried :: ( *… → a ) → ( *… → a )

### withNamedLock

**Signature:** `withNamedLock(...$name, ...$returnFn, ...$fn)`



Curried :: String → ( *… → String ) → ( *… → a ) → ( *… → a )
 Creates a new function that is *lockedso that it wont be called recursively. Multiple functions can use the same lock so they are blocked from calling each other recursively
 ```php
 $lockName = 'my-lock';
 $addOne = Fns::withNamedLock(
 $lockName,
 Fns::identity(),
 function ( $x ) use ( &$addOne ) { return $addOne( $x + 1 ); }
 );
 $this->assertEquals( 13, $addOne( 12 ), 'Should not recurse' );
 $addTwo = Fns::withNamedLock(
 $lockName,
 Fns::identity(),
 function ( $x ) use ( $addOne ) { return pipe( $addOne, $addOne) ( $x ); }
 );
 $this->assertEquals( 10, $addTwo( 10 ), 'Should return 10 because $addOne is locked by the same name as $addTwo' );
 ```
 *

### withoutRecursion

**Signature:** `withoutRecursion(...$returnFn, ...$fn)`



Curried :: ( *… → String ) → ( *… → a ) → ( *… → a )

### liftA2

**Signature:** `liftA2(...$fn, ...$monadA, ...$monadB)`



Curried :: ( a → b → c ) → m a → m b → m c

### liftA3

**Signature:** `liftA3(...$fn, ...$monadA, ...$monadB, ...$monadC)`



Curried :: ( a → b → c → d ) → m a → m b → m c → m d

### liftN

**Signature:** `liftN(...$n, ...$fn, ...$monad)`



Curried :: Number->( ( ) → a ) → ( *m ) → m a
 *

### until

**Signature:** `until(...$predicate, ...$fns)`



Curried :: ( b → bool ) → [( a → b )] → a → b
 *


* Json
### __call




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### __callStatic




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### hasMacro




Checks if macro is registered. 

 

**Parameters**

* `(string) $name`

**Return Values**

`bool`






### init



 init (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### macro




Register a custom macro. 

 

**Parameters**

* `(string) $name`
* `(callable) $macro`

**Return Values**

`void`






### toArray

**Signature:** `toArray(string ...$str)`



Curried :: json -> array

### toCollection

**Signature:** `toCollection(string ...$str)`

Curried :: json -> null | Collection


* Lens
### __call




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### __callStatic




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### hasMacro




Checks if macro is registered. 

 

**Parameters**

* `(string) $name`

**Return Values**

`bool`






### init



 init (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### macro




Register a custom macro. 

 

**Parameters**

* `(string) $name`
* `(callable) $macro`

**Return Values**

`void`






### iso

**Signature:** `iso(...$to, ...$from)`



Curried :: callable->callable->callable

### isoIdentity

**Signature:** `isoIdentity()`

:: callable->callable->callable

### isoUnserialized

**Signature:** `isoUnserialized()`

:: callable->callable->callable

### isoJsonDecoded

**Signature:** `isoJsonDecoded()`

:: callable->callable->callable

### isoUrlDecoded

**Signature:** `isoUrlDecoded()`

:: callable->callable->callable

### isoBase64Decoded

**Signature:** `isoBase64Decoded()`

:: callable->callable->callable

### isoParsedUrl

**Signature:** `isoParsedUrl()`

:: callable->callable->callable

### isoParsedQuery

**Signature:** `isoParsedQuery()`

:: callable->callable->callable


* Logic
### __call




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### __callStatic




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### hasMacro




Checks if macro is registered. 

 

**Parameters**

* `(string) $name`

**Return Values**

`bool`






### init



 init (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### macro




Register a custom macro. 

 

**Parameters**

* `(string) $name`
* `(callable) $macro`

**Return Values**

`void`






### not

**Signature:** `not(mixed ...$v)`



Curried :: mixed->bool

### isNotNull

**Signature:** `isNotNull(mixed ...$v)`



Curried :: mixed->bool

### ifElse

**Signature:** `ifElse(...$predicate, ...$first, ...$second, ...$data)`



Curried :: ( a->bool )->callable->callable->callable

### when

**Signature:** `when(...$predicate, ...$fn)`



Curried :: ( a->bool )->callable->callable

### unless

**Signature:** `unless(...$predicate, ...$fn)`



Curried :: ( a->bool )->callable->callable

### cond

**Signature:** `cond(...$conditions, ...$fn)`



Curried :: [( a->bool ), callable]->callable

### both

**Signature:** `both(...$a, ...$b, ...$data)`



Curried :: ( a → bool ) → ( a → bool ) → a → bool

### allPass

**Signature:** `allPass(...$predicates, ...$data)`



Curried :: [( *… → bool )] → ( *… → bool )

### anyPass

**Signature:** `anyPass(...$predicates, ...$data)`



Curried :: [( *… → bool )] → ( *… → bool )

### complement

**Signature:** `complement(...$fn)`



Curried :: ( *… → ) → ( *… → bool )

### defaultTo

**Signature:** `defaultTo(...$a, ...$b)`



Curried :: a → b → a | b

### either

**Signature:** `either(...$a, ...$b)`



Curried :: ( *… → bool ) → ( *… → bool ) → ( *… → bool )

### until

**Signature:** `until(...$predicate, ...$transform, ...$data)`



Curried :: ( a → bool ) → ( a → a ) → a → a

### propSatisfies

**Signature:** `propSatisfies(...$predicate, ...$prop, ...$data)`



Curried :: ( a → bool ) → String → [String => a] → bool

### isArray

**Signature:** `isArray(...$a)`



Curried :: a → bool

### isMappable

**Signature:** `isMappable(...$a)`



Curried :: a → bool

### isEmpty

**Signature:** `isEmpty(...$a)`



Curried :: a → bool

### isNotEmpty

**Signature:** `isNotEmpty(...$a)`



Curried :: a → bool

### firstSatisfying

**Signature:** `firstSatisfying(...$predicate, ...$functions, ...$data)`



Curried :: callable->callable[]->mixed->mixed

### isTruthy

**Signature:** `isTruthy(...$data)`



Curried :: mixed->bool


* Lst
### __call




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### __callStatic




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### diff




This method will return the values in the original collection that are not present in the given collection: 

 

**Parameters**

* `(array|\Collection) $array1`
* `(array|\Collection) $array2`

**Return Values**

`callable|\Collection|array`






### hasMacro




Checks if macro is registered. 

 

**Parameters**

* `(string) $name`

**Return Values**

`bool`






### init



 init (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### keyBy




Curried function that keys the array by the given key 

keyBy :: string -> array -> array  
  
$data = [  
   [ 'x' => 'a', 'y' => 123 ],  
   [ 'x' => 'b', 'y' => 456 ],  
];  
  
Lst::keyBy( 'x', $data );  
[  
   'a' => [ 'x' => 'a', 'y' => 123 ],  
   'b' => [ 'x' => 'b', 'y' => 456 ],  
],  

**Parameters**

* `(string) $key`
* `(array) $array`

**Return Values**

`array|callable`






### keyWith




Curried function that wraps each item in array with pair: [$key => $item1] 

keyWith :: string -> array -> array  
  
$data = [ 1, 2.3, 'some data', - 2, 'a' ];  
  
Lst::keyWith('myKey', $data);  
[ [ 'myKey' => 1 ], [ 'myKey' => 2.3 ], [ 'myKey' => 'some data' ], [ 'myKey' => - 2 ], [ 'myKey' => 'a' ] ]  

**Parameters**

* `(string) $key`
* `(array) $array`

**Return Values**

`array|callable`






### macro




Register a custom macro. 

 

**Parameters**

* `(string) $name`
* `(callable) $macro`

**Return Values**

`void`






### repeat




It returns array of $val elements repeated $times times. 

 

**Parameters**

* `(mixed) $val`
* `(int) $times`

**Return Values**

`callable|mixed`






### sum



 sum (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### append

**Signature:** `append(mixed ...$newItem, array ...$data)`



Curried :: mixed->array->array

### fromPairs

**Signature:** `fromPairs(array ...$array)`



Curried :: [[a, b]] → [a => b]

### toObj

**Signature:** `toObj(array ...$array)`



Curried :: array → object

### pluck

**Signature:** `pluck(...$prop, ...$array)`



Curried :: string → array → array

### partition

**Signature:** `partition(...$predicate, ...$target)`



Curried :: ( a → bool ) → [a] → [[a], [a]]

### sort

**Signature:** `sort(...$fn, ...$target)`



Curried :: ( ( a, a ) → int|bool ) → [a] → [a]

### unfold

**Signature:** `unfold(...$fn, ...$seed)`



Curried :: ( a → [b] ) → → [b]

### zip

**Signature:** `zip(...$a, ...$b)`



Curried :: [a] → [b] → [[a, b]]

### zipObj

**Signature:** `zipObj(...$a, ...$b)`



Curried :: [a] → [b] → [a => b]

### zipWith

**Signature:** `zipWith(...$f, ...$a, ...$b)`



Curried :: ( ( a, b ) → c ) → [a] → [b] → [c]

### join

**Signature:** `join(...$glue, ...$array)`



Curried :: string → [a] → string

### joinWithCommasAndAnd

**Signature:** `joinWithCommasAndAnd(...$array)`



Curried :: [a] → string

### concat

**Signature:** `concat(...$a, ...$b)`



Curried :: [a] → [a] → [a]

### find

**Signature:** `find(...$predicate, ...$array)`



Curried :: ( a → bool ) → [a] → a | null

### flattenToDepth

**Signature:** `flattenToDepth(...$depth, ...$array)`



Curried :: int → [[a]] → [a]

### flatten

**Signature:** `flatten(...$array)`



Curried :: [[a]] → [a]

### includes

**Signature:** `includes(...$val, ...$array)`



Curried :: a → [a] → bool

### includesAll

**Signature:** `includesAll(...$values, ...$array)`



Curried :: [a] → [a] → bool
 Determines if all the values are in the given array
 ```
 $includes10and20 = Lst::includesAll( [ 10, 20 ] );
 $this->assertTrue( $includes10and20( [ 5, 10, 15, 20 ] ) );
 $this->assertFalse( $includes10and20( [ 5, 15, 20 ] ) );
 ```

### nth

**Signature:** `nth(...$n, ...$array)`



Curried :: int → [a] → a | null

### first

**Signature:** `first(...$array)`



Curried :: [a, b] → a | null

### last

**Signature:** `last(...$array)`



Curried :: [a, b] → b | null

### length

**Signature:** `length(...$array)`



Curried :: [a] → int

### take

**Signature:** `take(...$n, ...$array)`



Curried :: int → [a] → [a]

### takeLast

**Signature:** `takeLast(...$n, ...$array)`



Curried :: int → [a] → [a]

### slice

**Signature:** `slice(...$offset, ...$limit, ...$array)`



Curried :: int → int->[a] → [a]

### drop

**Signature:** `drop(...$n, ...$array)`



Curried :: int → [a] → [a]

### dropLast

**Signature:** `dropLast(...$n, ...$array)`



Curried :: int → [a] → [a]

### makePair

**Signature:** `makePair(...$a, ...$b)`



Curried :: mixed → mixed → array

### make

**Signature:** `make(...$a)`



Curried :: mixed → array

### insert

**Signature:** `insert(...$index, ...$v, ...$array)`



Curried :: int → mixed → array → array

### range

**Signature:** `range(...$from, ...$to)`



Curried :: int → int → array

### xprod

**Signature:** `xprod(...$a, ...$b)`



Curried :: [a]->[b]->[a, b]
 Creates a new list out of the two supplied by creating each possible pair from the lists.
 ```
 $a              = [ 1, 2, 3 ];
 $b              = [ 'a', 'b', 'c' ];
 $expectedResult = [
 [ 1, 'a' ], [ 1, 'b' ], [ 1, 'c' ],
 [ 2, 'a' ], [ 2, 'b' ], [ 2, 'c' ],
 [ 3, 'a' ], [ 3, 'b' ], [ 3, 'c' ],
 ];
 $this->assertEquals( $expectedResult, Lst::xprod( $a, $b ) );
 ```

### prepend

**Signature:** `prepend(...$val, ...$array)`



Curried :: a → [a] → [a]
 Returns a new array with the given element at the front, followed by the contents of the list.
 *

### reverse

**Signature:** `reverse(...$array)`



Curried :: [a] → [a]
 Returns a new array with the elements reversed.
 *


* Math
### __call




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### __callStatic




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### hasMacro




Checks if macro is registered. 

 

**Parameters**

* `(string) $name`

**Return Values**

`bool`






### init



 init (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### macro




Register a custom macro. 

 

**Parameters**

* `(string) $name`
* `(callable) $macro`

**Return Values**

`void`






### multiply

**Signature:** `multiply(...$a, ...$b)`



Curried :: Number → Number → Number

### divide

**Signature:** `divide(...$a, ...$b)`



Curried :: Number → Number → Number

### add

**Signature:** `add(...$a, ...$b)`



Curried :: Number → Number → Number

### product

**Signature:** `product(...$array)`



Curried :: [Number] → Number


* Maybe
### fromNullable





Curried :: a → Nothing | Just a
 if $value is null or false it returns a Nothing otherwise returns a Just containing the value
 *


### safe





Curried :: ( a → b ) → ( a → Maybe b )
 returns a function that when called will run the passed in function and put the result into a Maybe
 *


### safeAfter





Curried :: ( b → bool ) → ( a → b ) → ( a → Maybe b )
 returns a function that when called will run the passed in function and pass the result of the function
 to the predicate. If the predicate returns true the result will be a Just containing the result of the function.
 Otherwise it returns a Nothing if the predicate returns false.
 *


### safeBefore





Curried :: ( a → bool ) → ( a → b ) → ( a → Maybe b )
 returns a function that when called will pass the given value to the predicate.
 If the predicate returns true the value will be lifted into a Just instance and
 the passed in function will then be mapped.
 Otherwise it returns a Nothing if the predicate returns false.
 *


### just





Curried :: a → Just a
 returns a Just containing the value.
 *


### of





Curried :: a → Just a
 returns a Just containing the value.
 *




* Obj
### __call




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### __callStatic




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### hasMacro




Checks if macro is registered. 

 

**Parameters**

* `(string) $name`

**Return Values**

`bool`






### init



 init (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### macro




Register a custom macro. 

 

**Parameters**

* `(string) $name`
* `(callable) $macro`

**Return Values**

`void`






### merge




Curried :: array|object -> array|object -> array|object 

It merges the new data with item. 

**Parameters**

* `(array|object) $newData`
* `(array|object) $item`

**Return Values**

`array|object`






### without




Curried :: mixed → array|object|Collection → array|object|Collection function to remove an item by key from an array. 

 

**Parameters**

* `(string|int) $key`
* `(array|object|\Collection|null) $item`

**Return Values**

`callable|array|object|\Collection`






### prop

**Signature:** `prop(...$key, ...$obj)`



Curried :: string->Collection|array|object->mixed|null

### propOr

**Signature:** `propOr(...$default, ...$key, ...$obj)`



Curried :: mixed->string->Collection|array|object->mixed|null

### props

**Signature:** `props(...$keys, ...$obj)`



Curried :: [keys] → Collection|array|object → [v]

### addProp

**Signature:** `addProp(...$key, ...$transformation, ...$obj)`



Curried :: string->callable->object|array->object->array

### removeProp

**Signature:** `removeProp(...$key, ...$obj)`



Curried :: string->object|array->object->array

### renameProp

**Signature:** `renameProp(...$key, ...$newKey, ...$obj)`



Curried :: string->string->object|array->object->array

### path

**Signature:** `path(...$path, ...$obj)`



Curried :: array->Collection|array|object->mixed|null

### pathOr

**Signature:** `pathOr(...$default, ...$path, ...$obj)`



Curried :: mixed → array → Collection|array|object → mixed

### assoc

**Signature:** `assoc(...$key, ...$value, ...$item)`



Curried :: string->mixed->Collection|array|object->mixed|null

### assocPath

**Signature:** `assocPath(...$path, ...$value, ...$item)`



Curried :: array->mixed->Collection|array|object->mixed|null

### lens

**Signature:** `lens(...$getter, ...$setter)`



Curried :: callable->callable->callable

### lensProp

**Signature:** `lensProp(...$prop)`



Curried :: string->callable

### lensPath

**Signature:** `lensPath(...$path)`



Curried :: array->callable

### lensMapped

**Signature:** `lensMapped(...$toFunctorFn)`



Curried :: callable->callable

### lensMappedProp

**Signature:** `lensMappedProp(...$prop)`



Curried :: string->callable

### view

**Signature:** `view(...$lens, ...$obj)`



Curried :: callable->Collection|array|object->mixed

### set

**Signature:** `set(...$lens, ...$value, ...$obj)`



Curried :: callable->mixed->Collection|array|object->mixed

### over

**Signature:** `over(...$lens, ...$transformation, ...$obj)`



Curried :: callable->callable->Collection|array|object->mixed

### pick

**Signature:** `pick(...$props, ...$obj)`



Curried :: array->Collection|array->Collection|array

### pickAll

**Signature:** `pickAll(...$props, ...$obj)`



Curried :: array->Collection|array->Collection|array

### pickBy

**Signature:** `pickBy(...$predicate, ...$obj)`



Curried :: ( ( v, k ) → bool ) → Collection|array->Collection|array

### pickByKey

**Signature:** `pickByKey(...$predicate, ...$obj)`



Curried :: ( ( k ) → bool ) → Collection|array->callable|Collection|array|object

### project

**Signature:** `project(...$props, ...$target)`



Curried :: array->Collection|array->Collection|array

### where

**Signature:** `where(array $condition)`



Curried :: [string → ( → bool )] → bool

### has

**Signature:** `has(...$prop, ...$item)`



Curried :: string → a → bool

### hasPath

**Signature:** `hasPath(...$path, ...$item)`



Curried :: array<string> → a → bool

### evolve

**Signature:** `evolve(...$transformations, ...$item)`



Curried :: array → array → array
 *

### objOf

**Signature:** `objOf(...$key, ...$value)`



Curried :: string->mixed->array
 Creates an object containing a single key:value pair.
 *

### keys

**Signature:** `keys(...$obj)`



Curried :: object|array->array
 Returns
 - keys if argument is an array
 - public properties' names if argument is an object
 - keys if argument is Collection
 ```
 $this->assertEquals( [ 0, 1, 2 ], Obj::keys( [ 'a', 'b', 'c' ] ) );
 $this->assertEquals( [ 'a', 'b', 'c' ], Obj::keys( [ 'a' => 1, 'b' => 2, 'c' => 3 ] ) );
 $this->assertEquals( [ 0, 1, 2 ], Obj::keys( \wpml_collect( [ 'a', 'b', 'c' ] ) ) );
 $this->assertEquals( [ 'a', 'b', 'c' ], Obj::keys( \wpml_collect( [ 'a' => 1, 'b' => 2, 'c' => 3 ] ) ) );
 $this->assertEquals( [ 'a', 'b', 'c' ], Obj::keys( (object) [ 'a' => 1, 'b' => 2, 'c' => 3 ] ) );
 ```
 *

### values

**Signature:** `values(...$obj)`



Curried :: object|array->array
 Returns
 - values if argument is an array
 - public properties' values if argument is an object
 - values if argument is Collection
 ```
 $this->assertEquals( [ 'a', 'b', 'c' ], Obj::values( [ 'a', 'b', 'c' ] ) );
 $this->assertEquals( [ 1, 2, 3 ], Obj::values( [ 'a' => 1, 'b' => 2, 'c' => 3 ] ) );
 $this->assertEquals( [ 'a', 'b', 'c' ], Obj::values( \wpml_collect( [ 'a', 'b', 'c' ] ) ) );
 $this->assertEquals( [ 1, 2, 3 ], Obj::values( \wpml_collect( [ 'a' => 1, 'b' => 2, 'c' => 3 ] ) ) );
 $this->assertEquals( [ 1, 2, 3 ], Obj::values( (object) [ 'a' => 1, 'b' => 2, 'c' => 3 ] ) );
 ```
 *

### replaceRecursive

**Signature:** `replaceRecursive(array ...$newValue, ...$target)`



Curried :: array->array->array
 *

### toArray

**Signature:** `toArray(Collection|Object ...$item)`



Curried :: Collection|Object->array


* Promise

* Relation
### __call




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### __callStatic




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### hasMacro




Checks if macro is registered. 

 

**Parameters**

* `(string) $name`

**Return Values**

`bool`






### init



 init (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### macro




Register a custom macro. 

 

**Parameters**

* `(string) $name`
* `(callable) $macro`

**Return Values**

`void`






### equals

**Signature:** `equals(...$a, ...$b)`



Curried :: a->b->bool

### lt

**Signature:** `lt(...$a, ...$b)`



Curried :: a->b->bool

### lte

**Signature:** `lte(...$a, ...$b)`



Curried :: a->b->bool

### gt

**Signature:** `gt(...$a, ...$b)`



Curried :: a->b->bool

### gte

**Signature:** `gte(...$a, ...$b)`



Curried :: a->b->bool

### propEq

**Signature:** `propEq(...$prop, ...$value, ...$obj)`



Curried :: String → a → array → bool

### sortWith

**Signature:** `sortWith(...$comparators, ...$array)`



Curried :: [(a, a) → int] → [a] → [a]


* Str
### __call




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### __callStatic




Dynamically handle calls to the class. 

 

**Parameters**

* `(string) $method`
* `(array) $parameters`

**Return Values**

`mixed`




**Throws Exceptions**


`\BadMethodCallException`




### hasMacro




Checks if macro is registered. 

 

**Parameters**

* `(string) $name`

**Return Values**

`bool`






### init



 init (void)

 

 

**Parameters**

`This function has no parameters.`

**Return Values**

`void`




### macro




Register a custom macro. 

 

**Parameters**

* `(string) $name`
* `(callable) $macro`

**Return Values**

`void`






### truncate_bytes




Truncates a string to a maximum number of bytes keeping multibyte chars integrity. 

 

**Parameters**

* `(string) $string`
* `(int) $max_bytes`
* `(int|null) $max_characters`

**Return Values**

`string`






### tail

**Signature:** `tail(string ...$str)`



Curried :: string->string

### split

**Signature:** `split(...$delimiter, ...$str)`



Curried :: string->string->string

### parse

**Signature:** `parse(...$string)`



Curried :: string → array

### includes

**Signature:** `includes(...$needle, ...$str)`



Curried :: string → string → bool

### trim

**Signature:** `trim(...$trim, ...$str)`



Curried :: string → string → string

### trimPrefix

**Signature:** `trimPrefix(...$trim, ...$str)`



Curried :: string → string → string
 Trims the prefix from the start of the string if the prefix exists
 ```
 $trimmed = Str::trimPrefix( 'prefix-', 'prefix-test' );
 ```
 *

### concat

**Signature:** `concat(...$a, ...$b)`



Curried :: string → string → string

### sub

**Signature:** `sub(...$start, ...$str)`



Curried :: int → string → string

### startsWith

**Signature:** `startsWith(...$test, ...$str)`



Curried :: string → string → bool

### endsWith

**Signature:** `endsWith(...$test, ...$str)`



Curried :: string → string → bool

### pos

**Signature:** `pos(...$test, ...$str)`



Curried :: string → string → int

### len

**Signature:** `len(...$str)`



Curried :: string → int

### replace

**Signature:** `replace(...$find, ...$replace, ...$str)`



Curried :: string → string → string → string

### pregReplace

**Signature:** `pregReplace(...$pattern, ...$replace, ...$str)`



Curried :: string → string → string → string

### match

**Signature:** `match(...$pattern, ...$str)`



Curried :: string → string → array

### matchAll

**Signature:** `matchAll(...$pattern, ...$str)`



Curried :: string → string → array

### wrap

**Signature:** `wrap(...$before, ...$after, ...$str)`



Curried :: string → string → string

### toUpper

**Signature:** `toUpper(string ...$str)`



Curried :: string → string

### toLower

**Signature:** `toLower(string ...$str)`



Curried :: string → string
 Wraps a string inside 2 other strings
 ```
 $wrapsInDiv = Str::wrap( '<div>', '</div>' );
 $wrapsInDiv( 'To be wrapped' ); // '<div>To be wrapped</div>'
 ```
 *


* Wrapper

