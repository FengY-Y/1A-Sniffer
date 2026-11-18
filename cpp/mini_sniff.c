/* 实验 1A 冒烟程序：验证 libpcap 环境是否可用。
 *
 *   gcc -O2 -o mini_sniff mini_sniff.c -lpcap
 *   sudo ./mini_sniff eth0 20
 *
 * 能打印出 20 个包（另开终端 ping 一下），说明环境通了，可以开始写正式代码。
 */
#include <pcap.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    const char *dev = (argc > 1) ? argv[1] : "eth0";
    int want = (argc > 2) ? atoi(argv[2]) : 20;
    char errbuf[PCAP_ERRBUF_SIZE];

    pcap_t *h = pcap_create(dev, errbuf);
    if (!h) {
        fprintf(stderr, "pcap_create: %s\n", errbuf);
        return 1;
    }
    pcap_set_snaplen(h, 262144);
    pcap_set_promisc(h, 1);
    pcap_set_timeout(h, 100);
    pcap_set_buffer_size(h, 32 * 1024 * 1024);

    int rc = pcap_activate(h);
    if (rc < 0) {
        fprintf(stderr, "pcap_activate: %s\n", pcap_geterr(h));
        pcap_close(h);
        return 1;
    }

    printf("dev=%s  linktype=%d  promisc=on\n", dev, pcap_datalink(h));

    struct pcap_pkthdr *hdr;
    const u_char *pkt;
    int n = 0;
    while (n < want && pcap_next_ex(h, &hdr, &pkt) >= 0) {
        if (hdr == NULL) continue;           /* 超时，没有包 */
        n++;
        printf("%3d  %ld.%06ld  caplen=%4u  len=%4u  ", n,
               (long)hdr->ts.tv_sec, (long)hdr->ts.tv_usec,
               hdr->caplen, hdr->len);
        for (unsigned i = 0; i < 6 && i < hdr->caplen; i++) printf("%02x ", pkt[i]);
        printf("\n");
    }

    struct pcap_stat st;
    if (pcap_stats(h, &st) == 0)
        printf("stats: recv=%u drop=%u ifdrop=%u\n", st.ps_recv, st.ps_drop, st.ps_ifdrop);
    pcap_close(h);
    return 0;
}
