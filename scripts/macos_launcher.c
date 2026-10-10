/* The macOS app's own executable ("Markdown Cornell Notes.app"'s
 * Contents/MacOS/markdown-cornell-notes): starts the Python bundled in
 * Contents/Resources on the editor app, passing its arguments along.
 *
 * A shell script could do the same, but a script can't carry the code
 * signature an .app's main executable needs. scripts/build_macos.sh
 * cross-compiles this from Linux with zig.
 */
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char path[PATH_MAX], real[PATH_MAX], python[PATH_MAX], script[PATH_MAX];
    uint32_t size = sizeof path;
    if (_NSGetExecutablePath(path, &size) != 0 || realpath(path, real) == NULL) {
        perror("markdown-cornell-notes: can't find its own location");
        return 1;
    }
    const char *macos_dir = dirname(real); /* .../Contents/MacOS */
    snprintf(python, sizeof python, "%s/../Resources/python/bin/python3", macos_dir);
    snprintf(script, sizeof script, "%s/../Resources/pipeline/app/main.py", macos_dir);

    char **args = calloc((size_t)argc + 2, sizeof *args);
    if (args == NULL) {
        return 1;
    }
    args[0] = python;
    args[1] = script;
    for (int i = 1; i < argc; i++) {
        args[i + 1] = argv[i];
    }
    execv(python, args);
    perror(python);
    return 1;
}
