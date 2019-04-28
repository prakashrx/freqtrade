#!/usr/bin/env bash
#encoding=utf8

function run_container() {

    args="-d"
    strategy="Ichimoku"
    for var in "$@"
    do
        case $var in
        -i)
            args="-it --entrypoint /bin/bash"
            ;;
        -p)
            prod=1
            ;;
        esac
    done
    
    mkdir -p user_data/data/history

    if [ $prod ]; then
        echo "***Starting freqtrade container(PROD)***"
        docker stop freqtrade > /dev/null
        docker rm freqtrade > /dev/null
        
        touch user_data/trades/prod/tradesv3.sqlite

        docker run $args \
                -v /etc/localtime:/etc/localtime:ro \
                -v $(pwd)/config.prod.json:/freqtrade/config.json \
                -v $(pwd)/user_data/trades/prod/tradesv3.sqlite:/freqtrade/user_data/trades/prod/tradesv3.sqlite \
                -v $(pwd)/user_data/data/history:/freqtrade/user_data/data/history \
                -v $(pwd)/user_data/strategies:/freqtrade/user_data/strategies \
                --name freqtrade \
                --restart unless-stopped \
                freqtrade \
                -s $strategy
    else
        echo "***Starting freqtrade container(DEV)***"
        docker stop freqtrade > /dev/null
        docker rm freqtrade > /dev/null

        touch user_data/trades/dryrun/tradesv3.dryrun.sqlite
        docker run $args \
            -v /etc/localtime:/etc/localtime:ro \
            -v $(pwd)/config.json:/freqtrade/config.json \
            -v $(pwd)/user_data/trades/dryrun/tradesv3.dryrun.sqlite:/freqtrade/user_data/trades/dryrun/tradesv3.dryrun.sqlite \
            -v $(pwd)/user_data/data/history:/freqtrade/user_data/data/history \
            -v $(pwd)/user_data/strategies:/freqtrade/user_data/strategies \
            --name freqtrade \
            --restart unless-stopped \
            freqtrade \
            -s $strategy
    fi

}

function run_backtest() {
    config="config.json"
    strategy="Ichimoku"
    freqtrade -c $config -s $strategy backtesting $*
}

function run_hyperopt() {
    config="config.json"
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
        esac
    done

    rm -f user_data/hyperopt_results.pickle
    rm -f user_data/hyperopt_tickerdata.pkl
    rm -f user_data/freqtrade-plot.html
    rm -f user_data/trades/dryrun/tradesv3.dryrun.sqlite
    touch user_data/trades/dryrun/tradesv3.dryrun.sqlite

    if [ $prod ]; then

        read -p "Delete prod tradesv3.sqlite. Are you sure?[No/Yes)?" choice
        case "$choice" in 
            Yes) 
            rm -f user_data/trades/prod/tradesv3.sqlite
            touch user_data/trades/prod/tradesv3.sqlite
            echo "Deleted Prod tradesv3.sqlite"
            ;;
        esac
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
            help
            exit 1
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
    echo "./start.sh container                  Run docker container"
    echo "./start.sh container -p               Run docker container in Production"
    echo "./start.sh container -i               Run docker container interactively"
    echo "./start.sh container -i -p            Run docker container interactively in Production"
    echo "./start.sh                            Run freqtrade dev locally"
    echo "./start.sh backtest                   Run freqtrade backtesting"
    echo "./start.sh hyperopt N                 Run freqtrade hyper optimization N times"
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