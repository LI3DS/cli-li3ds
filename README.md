# cli-li3ds

[![Travis](https://img.shields.io/travis/LI3DS/cli-li3ds.svg?style=flat-square)]() [![license](https://img.shields.io/github/license/LI3DS/cli-li3ds.svg?style=flat-square)]()

This `cli-li3ds` project provides a Command Line Interface for interacting with the [LI³DS REST API](https://github.com/li3ds/api-li3ds). The CLI can for example be used to import [Micmac](https://github.com/micmacIGN/micmac)-produced datasets into the LI³DS datastore.

## Installation

1. Clone the repo:

   ```bash
   $ git clone git@github.com:LI3DS/cli-li3ds.git
   ```

1. Create a virtual env

   ```bash
   $ virtualenv li3ds
   ```

1. Install:

    ```bash
    (li3ds) $ cd cli-li3ds
    (li3ds) $ pip install -e .
    ```

1. Use:

    ```
    (li3ds) $ li3ds --help
    ```
