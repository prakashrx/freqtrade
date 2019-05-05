#!/usr/bin/env bash
#encoding=utf8

function run_local() {

    strategy="Ichimoku"
    env=""
    for var in "$@"
    do
        case $var in
        -p)
            prod=1
            ;;
        *)
            env=".$var"
            ;;
        esac
    done

    if [ $prod ]; then
        environment="PROD"
        config="config$env.prod.json"
    else
        environment="DEV"
        config="config$env.json"
    fi
    
    if ! [ -f $config ]; then
        echo "Could not find configuration :$config"
        return
    fi        

    echo "***Running freqtrade locally($environment)***"
    echo "Configuration: $config"
    echo "Strategy: $strategy"

    freqtrade -c $config -s $strategy
}

function run_container() {

    args="-d"
    strategy="Ichimoku"
    env=""
    for var in "$@"
    do
        case $var in
        -i)
            args="-it --entrypoint /bin/bash"
            ;;
        -p)
            prod=1
            ;;
        stop)
            stop=1
            ;;
        logs)
            logs=1
            ;;
        *)
            env=".$var"
            ;;
        esac
    done
    
    if [ $prod ]; then
        environment="PROD"
        config="config$env.prod.json"
        name="freqtrade${env//./-}"
        tradesdb="user_data/trades/prod/tradesv3$env.sqlite"
    else
        environment="DEV"
        config="config$env.json"
        name="freqtrade${env//./-}-dev"
        tradesdb="user_data/trades/dryrun/tradesv3.dryrun$env.sqlite"
    fi
    
    if ! [ -f $config ]; then
        echo "Could not find configuration :$config"
        return
    fi        

    if [ $stop ]; then
        echo "***Stopping freqtrade container($environment)***"
        echo "Configuration: $config"
        echo "Name: $name"
        echo "Trades DB: $tradesdb"

        echo "Stopping container $name"
        docker stop $name
        docker rm $name
        return
    fi

    if [ $logs ]; then
        echo "***Logs for freqtrade container($environment)***"
        echo "Configuration: $config"
        echo "Name: $name"
        echo "Trades DB: $tradesdb"
        docker logs -f $name --tail 1000
        return
    fi

    mkdir -p user_data/data/history

    echo "***Deploying freqtrade container($environment)***"
    echo "Configuration: $config"
    echo "Name: $name"
    echo "Trades DB: $tradesdb"

    echo "Stopping container $name"
    docker stop $name > /dev/null
    docker rm $name > /dev/null

    echo "Starting container $name"
    if ! [ -f $tradesdb ]; then
        echo "Could not find $tradesdb. Creating one."
        touch $tradesdb
    fi

    docker run $args \
            -v /etc/localtime:/etc/localtime:ro \
            -v $(pwd)/$config:/freqtrade/config.json \
            -v $(pwd)/$tradesdb:/freqtrade/$tradesdb \
            -v $(pwd)/user_data/data/history:/freqtrade/user_data/data/history \
            -v $(pwd)/user_data/strategies:/freqtrade/user_data/strategies \
            --name $name \
            --restart unless-stopped \
            freqtrade \
            -s $strategy
}

function run_backtest() {

    config="config.json"
    if [ -f "config.$1.json" ]; then
        config="config.$1.json"
        shift
    fi

    strategy="Ichimoku"
    echo "Using configuration $config. Strategy $strategy"
    freqtrade -c $config -s $strategy backtesting $*
}

function run_hyperopt() {
    config="config.json"
    if [ -f "config.$1.json" ]; then
        config="config.$1.json"
        shift
    fi

    optimizer="IchimokuOpts"

    n=$1
    shift

    for i in {1..n}; do freqtrade -c $config hyperopt --customhyperopt $optimizer -e 1000 $*; done
}


function download_data() {

    days=180
    timeframe="15m"
    python3 scripts/download_backtest_data.py --exchange binance --days $days --timeframes $timeframe
}

function clean() {

    for var in "$@"
    do
        case $var in
        -p)
            prod=1
            ;;
        *)
            env=".$var"
            ;;
        esac
    done

    if [ $prod ]; then
        environment="PROD"
        config="config$env.prod.json"
        tradesdb="user_data/trades/prod/tradesv3$env.sqlite"
    else
        environment="DEV"
        config="config$env.json"
        tradesdb="user_data/trades/dryrun/tradesv3.dryrun$env.sqlite"
    fi

    echo "***Cleaning freqtrade environment($environment)***"
    echo "Configuration: $config"
    echo "Name: $name"
    echo "Trades DB: $tradesdb"

    echo "***Cleaning hyperopt results...***"
    rm -f user_data/hyperopt_results.pickle
    rm -f user_data/hyperopt_tickerdata.pkl
    echo "***Cleaning plots...***"
    rm -f user_data/freqtrade-plot.html

    echo "***Cleaning trades for env ($config)...***"
    if [ $prod ]; then
        read -p "Delete prod tradesv3.sqlite. Are you sure?[No/Yes)?" choice
        case "$choice" in 
            Yes) 
                rm -f $tradesdb
                touch $tradesdb
                echo "Deleted Prod tradesv3.sqlite"
                ;;
        esac
    else
        rm -f $tradesdb
        touch $tradesdb
    fi
    

}

function run() {

    if [ -z "$*" ]
    then
        echo "Running freqtrade locally"
        config="config.json"
        strategy="Ichimoku"
        freqtrade -c $config -s $strategy
        exit 0
    fi

    case $1 in
        container)
            shift
            run_container $*
            ;;
        backtest)
            shift
            run_backtest $*
            ;;
        hyperopt)
            shift
            run_hyperopt $*
            ;;
        download)
            shift
            download_data $*
            ;;
        clean)
            shift
            clean $*
            ;;
        *)
            run_local $*
            ;;
    esac
}


function build() {
    name="freqtrade"
    tag=$(git describe --long --tags | sed 's/-g[a-z0-9]\{7\}//')
    if [ -z "$tag" ]
    then
      echo "\$tag is empty. unable to get tag from git describe"
      exit 1
    fi
    img="$name:$tag"
    latest="$name:latest"
    
    docker build -t $img .
    docker tag $img $latest
}

function help() {
    echo "usage:"
    echo "./start.sh build                      Build freqtrade docker image"
    echo "./start.sh container [NAME]           Run docker container"
    echo "./start.sh container [NAME] stop      Stop docker container"
    echo "./start.sh container [NAME] logs      Tail Logs from docker container"
    echo "./start.sh container [NAME] -p        Run docker container in Production"
    echo "./start.sh container [NAME] -i        Run docker container interactively"
    echo "./start.sh container [NAME] -i -p     Run docker container interactively in Production"
    echo "./start.sh                            Run freqtrade dev locally"
    echo "./start.sh backtest [NAME[.prod]]     Run freqtrade backtesting"
    echo "./start.sh hyperopt [NAME[.prod]] N   Run freqtrade hyper optimization N times"
    echo "./start.sh download [-d 180] [-t 4h]  Download data for given timeframe"
    echo "./start.sh clean                      Clean up workspace. Deletes dryrun.sqlite, hyperopt, plotting etc"
    echo "./start.sh clean -p                   Clean up workspace. Same as clean. Also cleans prod tradesv3.sqlite"
}

case $1 in
    build)
        build
        ;;
    -h | --help ) 
        help
        exit
        ;;
    * )
        run $*
        ;;
esac