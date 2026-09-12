#import <AVFoundation/AVFoundation.h>
#import <Foundation/Foundation.h>

void trigger_camera_prompt() {
    dispatch_semaphore_t sem = dispatch_semaphore_create(0);
    [AVCaptureDevice requestAccessForMediaType:AVMediaTypeVideo completionHandler:^(BOOL granted) {
        [AVCaptureDevice requestAccessForMediaType:AVMediaTypeAudio completionHandler:^(BOOL granted) {
            dispatch_semaphore_signal(sem);
        }];
    }];
    dispatch_semaphore_wait(sem, DISPATCH_TIME_FOREVER);
}
