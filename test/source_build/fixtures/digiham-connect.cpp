// GPL-3.0; excerpt from luarvique/digiham at beec78229edb8e049f8b82729498def952b79cc1
int MbeSynthesizer::connect(const std::string &path) {
    // unix domain sockets connection
    sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    const char* socket_path = "/tmp/codecserver.sock";
    strncpy(addr.sun_path, socket_path, strlen(socket_path));

    int sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock == -1) {
        throw ConnectionError("socket error: " + std::string(strerror(errno)));
    }

    struct timeval timeout {
        .tv_sec = 5,
        .tv_usec = 0
    };
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

    if (::connect(sock, (struct sockaddr*) &addr, sizeof(addr)) == -1) {
        throw ConnectionError("connection failure: " + std::string(strerror(errno)));
    }

    return sock;
}
