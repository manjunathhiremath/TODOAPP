// Task deadline notification system

// Function to calculate time until deadline for a task
function calculateTimeUntilDeadline(deadlineString) {
    const deadline = new Date(deadlineString);
    const now = new Date();
    return deadline - now;
  }
  
  // Schedule notifications for tasks
  function scheduleTaskNotifications(tasks) {
    tasks.forEach(task => {
      const timeUntil = calculateTimeUntilDeadline(task.deadline);
      
      // Schedule 24-hour warning if applicable
      const dayMs = 24 * 60 * 60 * 1000;
      if (timeUntil > dayMs) {
        setTimeout(() => {
          showNotification(
            'Task Due Soon', 
            `Your task "${task.title}" is due in 24 hours.`,
            task.id
          );
        }, timeUntil - dayMs);
      }
      
      // Schedule 1-hour warning if applicable
      const hourMs = 60 * 60 * 1000;
      if (timeUntil > hourMs) {
        setTimeout(() => {
          showNotification(
            'Task Due Very Soon', 
            `Your task "${task.title}" is due in 1 hour.`,
            task.id
          );
        }, timeUntil - hourMs);
      }
      
      // Schedule deadline notification
      if (timeUntil > 0) {
        setTimeout(() => {
          showNotification(
            'Task Deadline Reached', 
            `Your task "${task.title}" is now due!`,
            task.id
          );
        }, timeUntil);
      }
    });
  }
  
  // Display notification
  function showNotification(title, body, taskId) {
    // Check if notifications are supported and permission is granted
    if (!("Notification" in window)) {
      console.log("This browser does not support notifications");
      return;
    }
    
    if (Notification.permission === "granted") {
      const notification = new Notification(title, {
        body: body,
        icon: '/static/icons/icon-192x192.png',
        tag: `task-${taskId}`
      });
      
      notification.onclick = function() {
        window.focus();
        // Redirect to the task completion page
        // This part will depend on your app's routing structure
        window.location.href = `/?task=${taskId}`;
      };
    } 
    else if (Notification.permission !== "denied") {
      Notification.requestPermission().then(permission => {
        if (permission === "granted") {
          showNotification(title, body, taskId);
        }
      });
    }
  }
  
  // Function to fetch tasks and schedule notifications
  function initializeNotifications() {
    // This would typically fetch from an API
    // For demonstration, we'll use an event listener instead
    
    window.addEventListener('tasksUpdated', function(e) {
      if (e.detail && e.detail.tasks) {
        scheduleTaskNotifications(e.detail.tasks);
      }
    });
    
    // Request notification permission
    if (Notification.permission !== "granted" && Notification.permission !== "denied") {
      Notification.requestPermission();
    }
  }
  
  // Initialize when the page loads
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeNotifications);
  } else {
    initializeNotifications();
  }