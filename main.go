package main

import (
	"bufio"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"sync"
	"time"
)

type cmd struct {
	description string
	help        string
	run         func()
}

var subcommands = map[string]cmd{
	"check": {
		"find working proxies given a list",
		"take a list of proxies in stdin in the form scheme://ip:port, prints working proxies",
		check,
	},
}

// TODO: Make CLI flags.
const (
	workers = 32
	retries = 3
)

func check() {
	var wg sync.WaitGroup
	working := make(chan string)
	go func() {
		for s := range working {
			fmt.Println(s)
		}
	}()

	// spawn workers
	proxies := make(chan string)
	wg.Add(workers)
	for i := 0; i < workers; i++ {
		go func() {
			defer wg.Done()

			for proxy := range proxies {
				client, err := newProxyClient(proxy)
				if err != nil {
					fmt.Fprintln(os.Stderr, err)
					continue
				}

				for i := 0; i < retries; i++ {
					resp, err := client.Get("https://ifconfig.me")
					if err != nil {
						fmt.Fprintln(os.Stderr, err)
						continue
					}
					resp.Body.Close()

					working <- proxy
					break
				}
			}
		}()
	}

	s := bufio.NewScanner(os.Stdin)
	for s.Scan() {
		proxies <- s.Text()
	}
	close(proxies)

	wg.Wait()
	close(working)
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "Usage: %s <command> [args...]\n", os.Args[0])
		return
	}

	subcommand := os.Args[1]
	switch subcommand {
	case "help", "-h", "--help":
		if len(os.Args) == 3 {
			if cmd, ok := subcommands[os.Args[2]]; ok {
				fmt.Fprintln(os.Stderr, cmd.help)
			} else {
				fmt.Fprintf(os.Stderr, "unknown subcommand: %q\n", os.Args[2])
			}
			return
		}

		fmt.Fprintf(os.Stderr, "Usage: %s <subcommand> [args...]\n\n", os.Args[0])
		fmt.Fprintln(os.Stderr, "Subcommands:")

		for name, cmd := range subcommands {
			fmt.Fprintf(os.Stderr, "\t%s\t%s\n", name, cmd.help)
		}
	default:
		if cmd, ok := subcommands[subcommand]; ok {
			cmd.run()
		}
	}
}

func newProxyClient(proxyURL string) (*http.Client, error) {
	url, err := url.Parse(proxyURL)
	if err != nil {
		return nil, err
	}

	client := &http.Client{
		Transport: &http.Transport{Proxy: http.ProxyURL(url)},
		Timeout:   time.Second * 10,
	}
	return client, nil
}
