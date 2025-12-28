/**
 * NogicOS Tool Implementations (Electron Side)
 * Handles file system, terminal, and other local operations
 * 
 * Inspired by Continue's tool system
 */

const fs = require('fs');
const path = require('path');
const { exec, spawn } = require('child_process');
const os = require('os');

/**
 * Resolve path with support for ~, relative, and absolute paths
 */
function resolvePath(inputPath) {
    if (!inputPath) return process.cwd();
    
    // Handle tilde paths
    if (inputPath.startsWith('~')) {
        return path.join(os.homedir(), inputPath.slice(1));
    }
    
    // Handle absolute paths
    if (path.isAbsolute(inputPath)) {
        return inputPath;
    }
    
    // Relative path - resolve from home directory for user-friendliness
    return path.resolve(os.homedir(), inputPath);
}

/**
 * Tool: Read File
 */
async function readFile(args) {
    const { filepath } = args;
    const resolvedPath = resolvePath(filepath);
    
    return new Promise((resolve, reject) => {
        fs.readFile(resolvedPath, 'utf-8', (err, data) => {
            if (err) {
                if (err.code === 'ENOENT') {
                    reject(new Error(`File not found: ${filepath}`));
                } else if (err.code === 'EACCES') {
                    reject(new Error(`Permission denied: ${filepath}`));
                } else {
                    reject(new Error(`Failed to read file: ${err.message}`));
                }
            } else {
                resolve({
                    filepath: resolvedPath,
                    content: data,
                    size: data.length
                });
            }
        });
    });
}

/**
 * Tool: Write File
 */
async function writeFile(args) {
    const { filepath, content } = args;
    const resolvedPath = resolvePath(filepath);
    
    // Ensure directory exists
    const dir = path.dirname(resolvedPath);
    
    return new Promise((resolve, reject) => {
        fs.mkdir(dir, { recursive: true }, (mkdirErr) => {
            if (mkdirErr && mkdirErr.code !== 'EEXIST') {
                reject(new Error(`Failed to create directory: ${mkdirErr.message}`));
                return;
            }
            
            fs.writeFile(resolvedPath, content, 'utf-8', (err) => {
                if (err) {
                    reject(new Error(`Failed to write file: ${err.message}`));
                } else {
                    resolve({
                        filepath: resolvedPath,
                        success: true,
                        message: `File written successfully: ${resolvedPath}`
                    });
                }
            });
        });
    });
}

/**
 * Tool: List Directory
 */
async function listDir(args) {
    const { dirpath, recursive } = args;
    const resolvedPath = resolvePath(dirpath || '.');
    
    return new Promise((resolve, reject) => {
        if (recursive) {
            // Recursive listing
            const results = [];
            walkDir(resolvedPath, results, '', (err) => {
                if (err) {
                    reject(new Error(`Failed to list directory: ${err.message}`));
                } else {
                    resolve({
                        dirpath: resolvedPath,
                        entries: results.slice(0, 200), // Limit to prevent huge outputs
                        truncated: results.length > 200
                    });
                }
            });
        } else {
            // Non-recursive listing
            fs.readdir(resolvedPath, { withFileTypes: true }, (err, entries) => {
                if (err) {
                    if (err.code === 'ENOENT') {
                        reject(new Error(`Directory not found: ${dirpath}`));
                    } else {
                        reject(new Error(`Failed to list directory: ${err.message}`));
                    }
                } else {
                    const items = entries.map(entry => ({
                        name: entry.name,
                        type: entry.isDirectory() ? 'directory' : 'file',
                        path: path.join(resolvedPath, entry.name)
                    }));
                    resolve({
                        dirpath: resolvedPath,
                        entries: items
                    });
                }
            });
        }
    });
}

/**
 * Helper: Walk directory recursively
 */
function walkDir(dir, results, prefix, callback) {
    fs.readdir(dir, { withFileTypes: true }, (err, entries) => {
        if (err) {
            callback(err);
            return;
        }
        
        let pending = entries.length;
        if (pending === 0) {
            callback(null);
            return;
        }
        
        entries.forEach(entry => {
            const relativePath = prefix ? `${prefix}/${entry.name}` : entry.name;
            results.push({
                name: entry.name,
                type: entry.isDirectory() ? 'directory' : 'file',
                path: relativePath
            });
            
            if (entry.isDirectory() && results.length < 500) {
                walkDir(path.join(dir, entry.name), results, relativePath, (walkErr) => {
                    pending--;
                    if (pending === 0) callback(null);
                });
            } else {
                pending--;
                if (pending === 0) callback(null);
            }
        });
    });
}

/**
 * Tool: Run Terminal Command
 */
async function runCommand(args) {
    const { command, wait_for_completion = true } = args;
    
    return new Promise((resolve, reject) => {
        if (wait_for_completion) {
            exec(command, { 
                timeout: 60000, // 60 second timeout
                maxBuffer: 1024 * 1024 * 10, // 10MB buffer
                cwd: os.homedir()
            }, (err, stdout, stderr) => {
                if (err) {
                    // Command failed but we still return the output
                    resolve({
                        success: false,
                        exitCode: err.code || 1,
                        stdout: stdout || '',
                        stderr: stderr || err.message,
                        command: command
                    });
                } else {
                    resolve({
                        success: true,
                        exitCode: 0,
                        stdout: stdout,
                        stderr: stderr,
                        command: command
                    });
                }
            });
        } else {
            // Run in background
            const child = spawn(command, [], {
                shell: true,
                detached: true,
                stdio: 'ignore',
                cwd: os.homedir()
            });
            child.unref();
            resolve({
                success: true,
                message: `Command started in background: ${command}`,
                pid: child.pid
            });
        }
    });
}

/**
 * Tool: Create Directory
 */
async function createDir(args) {
    const { dirpath } = args;
    const resolvedPath = resolvePath(dirpath);
    
    return new Promise((resolve, reject) => {
        fs.mkdir(resolvedPath, { recursive: true }, (err) => {
            if (err) {
                reject(new Error(`Failed to create directory: ${err.message}`));
            } else {
                resolve({
                    dirpath: resolvedPath,
                    success: true,
                    message: `Directory created: ${resolvedPath}`
                });
            }
        });
    });
}

/**
 * Tool Router - Execute tool by name
 */
async function executeTool(toolName, args) {
    switch (toolName) {
        case 'read_file':
            return await readFile(args);
        case 'write_file':
            return await writeFile(args);
        case 'list_dir':
            return await listDir(args);
        case 'run_command':
            return await runCommand(args);
        case 'create_dir':
            return await createDir(args);
        default:
            throw new Error(`Unknown tool: ${toolName}`);
    }
}

module.exports = {
    executeTool,
    readFile,
    writeFile,
    listDir,
    runCommand,
    createDir,
    resolvePath
};



