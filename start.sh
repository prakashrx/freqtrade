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
    
    if [ $prod ]; then
        echo "***Starting freqtrade container(PROD)***"
        docker stop freqtrade > /dev/null
        docker rm freqtrade > /dev/null
        docker run $args \
                -v /etc/localtime:/etc/localtime:ro \
                -v $(pwd)/config.prod.json:/freqtrade/config.json \
                -v $(pwd)/user_data/trades/prod/tradesv3.sqlite:/freqtrade/user_data/prod/tradesv3.sqlite \
                --name freqtrade \
                --restart unless-stopped
                freqtrade \
                -s $strategy
    else
        echo "***Starting freqtrade container(DEV)***"
        docker stop freqtrade > /dev/null
        docker rm freqtrade > /dev/null
        docker run $args \
            -v /etc/localtime:/etc/localtime:ro \
            -v $(pwd)/config.json:/freqtrade/config.json \
            -v $(pwd)/user_data/trades/dryrun/tradesv3.dryrun.sqlite:/freqtrade/user_data/trades/dryrun/tradesv3.dryrun.sqlite \
            --name freqtrade \
            --restart unless-stopped
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
    #rm -f user_data/hyperopt_results.pickle
    #rm -f user_data/hyperopt_tickerdata.pkl
    for i in {1..10}; do freqtrade -c $config hyperopt --customhyperopt $optimizer -e 1000 $*; done
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
    echo "./start.sh build              Build freqtrade docker image"
    echo "./start.sh container          Run docker container"
    echo "./start.sh container -p       Run docker container in Production"
    echo "./start.sh container -i       Run docker container interactively"
    echo "./start.sh container -i -p    Run docker container interactively in Production"
    echo "./start.sh                    Run freqtrade dev locally"
    echo "./start.sh backtest           Run freqtrade backtesting"
    echo "./start.sh hyperopt           Run freqtrade hyper optimization"
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