document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('uploadForm');
    const submitButton = form.querySelector('button[type="submit"]');
    const originalButtonText = submitButton.textContent;
    const fileInput = document.getElementById('file-upload');
    const dropZone = form.querySelector('.border-dashed');
    let originalImageUrl = null;
    
    // Image constraints
    const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB
    const MAX_DIMENSION = 4096; // Reasonable max dimension for client-side validation
    const SUPPORTED_FORMATS = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif'];
    
    // Validate image file
    function validateImage(file) {
        const errors = [];
        
        // Check file type
        if (!SUPPORTED_FORMATS.includes(file.type)) {
            errors.push('Please upload a valid image file (JPEG, PNG, WebP, or GIF)');
        }
        
        // Check file size
        if (file.size > MAX_FILE_SIZE) {
            const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
            errors.push(`Image size (${sizeMB}MB) exceeds maximum allowed size of 20MB`);
        }
        
        return errors;
    }
    
    // Validate image dimensions
    async function validateImageDimensions(file) {
        return new Promise((resolve) => {
            const img = new Image();
            const objectUrl = URL.createObjectURL(file);
            
            img.onload = function() {
                URL.revokeObjectURL(objectUrl);
                const errors = [];
                
                if (img.width > MAX_DIMENSION || img.height > MAX_DIMENSION) {
                    errors.push(`Image dimensions (${img.width}x${img.height}) are too large. Maximum dimension is ${MAX_DIMENSION}px. The image will be automatically resized.`);
                }
                
                resolve({ errors, width: img.width, height: img.height });
            };
            
            img.onerror = function() {
                URL.revokeObjectURL(objectUrl);
                resolve({ errors: ['Unable to read image dimensions'], width: 0, height: 0 });
            };
            
            img.src = objectUrl;
        });
    }
    
    // Show validation message
    function showValidationMessage(message, isError = true) {
        // Remove any existing validation message
        const existingMsg = document.querySelector('.validation-message');
        if (existingMsg) {
            existingMsg.remove();
        }
        
        // Create new message element
        const msgDiv = document.createElement('div');
        msgDiv.className = `validation-message mt-4 p-3 rounded-lg text-sm ${
            isError ? 'bg-red-100 text-red-700 border border-red-300' : 'bg-yellow-100 text-yellow-700 border border-yellow-300'
        }`;
        msgDiv.innerHTML = `
            <div class="flex items-start">
                <svg class="w-5 h-5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    ${isError ? 
                        '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>' :
                        '<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>'
                    }
                </svg>
                <div>${message}</div>
            </div>
        `;
        
        // Insert after the file input area
        const uploadArea = form.querySelector('.border-dashed').parentElement;
        uploadArea.insertAdjacentElement('afterend', msgDiv);
        
        // Auto-remove warning messages after 10 seconds
        if (!isError) {
            setTimeout(() => {
                msgDiv.remove();
            }, 10000);
        }
    }
    
    // Handle form submission (multiple files and variants)
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const files = Array.from(fileInput.files);
        const promptTextarea = document.getElementById('prompt');
        const variantsSelect = document.getElementById('variants');

        if (files.length === 0) {
            alert('Пожалуйста, выберите хотя бы один файл');
            return;
        }

        // Get parameters
        const size = form.querySelector('input[name="size"]:checked').value;
        const quality = form.querySelector('input[name="quality"]:checked').value;
        const model = document.getElementById('model').value;
        const numVariants = parseInt(variantsSelect.value);
        const prompt = promptTextarea.value || '';

        // Show loading state
        submitButton.disabled = true;
        submitButton.innerHTML = 'Обработка... <span class="loading"></span>';

        const resultDiv = document.getElementById('result');
        const resultsGrid = document.getElementById('resultsGrid');
        resultsGrid.innerHTML = '';

        // Remove any validation messages
        const validationMsg = document.querySelector('.validation-message');
        if (validationMsg) {
            validationMsg.remove();
        }

        try {
            // Show original images
            const originalImagesGrid = document.getElementById('originalImagesGrid');
            originalImagesGrid.innerHTML = '';
            window.originalImages.forEach((imgUrl, idx) => {
                const imgDiv = document.createElement('div');
                imgDiv.className = 'relative bg-white rounded-lg shadow-sm overflow-hidden';
                imgDiv.innerHTML = `
                    <img src="${imgUrl}" class="w-full h-20 object-cover" />
                    <p class="text-xs text-gray-600 p-1 text-center">#${idx + 1}</p>
                `;
                originalImagesGrid.appendChild(imgDiv);
            });

            // Generate multiple variants
            for (let variantIdx = 0; variantIdx < numVariants; variantIdx++) {
                submitButton.innerHTML = `Генерация варианта ${variantIdx + 1} из ${numVariants}... <span class="loading"></span>`;

                // Create FormData for this variant
                const formData = new FormData();

                // Add all files
                files.forEach(file => {
                    formData.append('files', file);
                });

                // Add variant-specific prompt with seed
                let variantPrompt = prompt;
                if (numVariants > 1) {
                    variantPrompt += ` (вариант ${variantIdx + 1})`;
                }

                formData.append('prompt', variantPrompt);
                formData.append('size', size);
                formData.append('quality', quality);
                formData.append('model', model);
                formData.append('seed', Date.now() + variantIdx);

                // Call API
                const response = await fetch('api/enhance-image-multi', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    let errorMsg = 'Ошибка при обработке варианта ' + (variantIdx + 1);
                    try {
                        const error = await response.json();
                        errorMsg = error.detail || errorMsg;
                    } catch (e) {}
                    throw new Error(errorMsg);
                }

                const blob = await response.blob();
                const imageUrl = URL.createObjectURL(blob);

                // Add result to grid
                const resultCard = document.createElement('div');
                resultCard.className = 'bg-white rounded-lg shadow-md p-4';
                resultCard.innerHTML = `
                    <div class="flex justify-between items-center mb-2">
                        <p class="text-sm font-medium text-gray-700">Вариант ${variantIdx + 1}</p>
                        <span class="text-xs text-green-600">✓ Готово</span>
                    </div>
                    <img src="${imageUrl}" class="w-full rounded-lg mb-3" />
                    <a href="${imageUrl}" download="variant_${variantIdx + 1}.png"
                       class="block text-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
                        Скачать
                    </a>
                `;
                resultsGrid.appendChild(resultCard);
            }

            resultDiv.classList.remove('hidden');
            resultDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });

        } catch (error) {
            showValidationMessage('Ошибка: ' + error.message, true);
            console.error('Enhancement error:', error);
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
        }
    });

    // Download all button
    document.addEventListener('DOMContentLoaded', function() {
        const downloadAllBtn = document.getElementById('downloadAllBtn');
        if (downloadAllBtn) {
            downloadAllBtn.addEventListener('click', async () => {
                const images = document.querySelectorAll('#resultsGrid img');
                images.forEach((img, idx) => {
                    setTimeout(() => {
                        const a = document.createElement('a');
                        a.href = img.src;
                        a.download = `variant_${idx + 1}.png`;
                        a.click();
                    }, idx * 500); // Delay between downloads
                });
            });
        }
    });
    
    // Preview uploaded images (multiple)
    fileInput.addEventListener('change', async function(e) {
        const files = Array.from(e.target.files);

        if (files.length === 0) return;

        // Check file count limit
        if (files.length > 20) {
            showValidationMessage('Максимум 20 файлов за раз. Выбрано: ' + files.length, true);
            fileInput.value = '';
            return;
        }

        // Clear previous previews
        const previewGallery = document.getElementById('previewGallery');
        previewGallery.innerHTML = '';

        // Update file count
        document.getElementById('fileCount').textContent = files.length;

        // Store original image URLs
        window.originalImages = [];

        let hasErrors = false;

        for (const file of files) {
            if (!file.type.startsWith('image/')) {
                showValidationMessage(`Файл ${file.name} не является изображением`, true);
                hasErrors = true;
                continue;
            }

            // Validate each file
            const validationErrors = validateImage(file);
            if (validationErrors.length > 0) {
                showValidationMessage(`${file.name}: ${validationErrors.join(', ')}`, true);
                hasErrors = true;
                continue;
            }

            // Validate dimensions
            const dimensionCheck = await validateImageDimensions(file);
            if (dimensionCheck.errors.length > 0) {
                showValidationMessage(`${file.name}: ${dimensionCheck.errors.join(', ')}`, false);
            }

            // Create thumbnail
            const reader = new FileReader();
            reader.onload = function(e) {
                const thumbnailDiv = document.createElement('div');
                thumbnailDiv.className = 'relative bg-white rounded-lg shadow-sm overflow-hidden';
                thumbnailDiv.innerHTML = `
                    <img src="${e.target.result}" class="w-full h-24 object-cover" />
                    <p class="text-xs text-gray-600 p-1 truncate" title="${file.name}">${file.name}</p>
                    <p class="text-xs text-gray-400 px-1 pb-1">${(file.size / 1024 / 1024).toFixed(2)}MB</p>
                `;
                previewGallery.appendChild(thumbnailDiv);
                window.originalImages.push(e.target.result);
            };
            reader.readAsDataURL(file);
        }

        if (hasErrors) {
            fileInput.value = '';
            document.getElementById('preview').classList.add('hidden');
        } else {
            document.getElementById('preview').classList.remove('hidden');
        }
    });
    
    // Drag and drop functionality
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight(e) {
        dropZone.classList.add('border-blue-400', 'bg-blue-50');
    }
    
    function unhighlight(e) {
        dropZone.classList.remove('border-blue-400', 'bg-blue-50');
    }
    
    dropZone.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0) {
            fileInput.files = files;
            const event = new Event('change', { bubbles: true });
            fileInput.dispatchEvent(event);
        }
    }
}); 