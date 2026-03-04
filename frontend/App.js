import React from 'react';
import { View, ActivityIndicator, StyleSheet, TouchableOpacity } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { useFonts, Outfit_600SemiBold, Outfit_400Regular } from '@expo-google-fonts/outfit';
import * as SplashScreen from 'expo-splash-screen';
import { NavigationContainer, StackActions } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import WelcomeScreen from './screens/WelcomeScreen';
import LoginScreen from './screens/LoginScreen';
import CreateAccountScreen from './screens/CreateAccountScreen';
import ClosetScreen from './screens/ClosetScreen';
import SavedShoesScreen from './screens/SavedShoesScreen';
import OwnedShoesScreen from './screens/OwnedShoesScreen';
import FootCaptureScreen from './screens/FootCaptureScreen';
import CameraScreen from './screens/CameraScreen';
import MeasurementsScreen from './screens/MeasurementsScreen';
import RecommendationsScreen from './screens/RecommendationsScreen';
import ProfileScreen from './screens/ProfileScreen';
import { SavedShoesProvider } from './SavedShoesContext';
// Keep the splash screen visible while we fetch resources
SplashScreen.preventAutoHideAsync();

const RootStack = createNativeStackNavigator();
const ClosetStack = createNativeStackNavigator();
const RecommendationsStack = createNativeStackNavigator();
const ProfileStack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const sharedHeaderOptions = {
  headerStyle: { backgroundColor: '#FFF8F0' },
  headerShadowVisible: false,
  headerTitleStyle: { fontFamily: 'Outfit_600SemiBold' },
};

const headerLeftBack = (navigation) => (
  <TouchableOpacity
    onPress={() => navigation.goBack()}
    style={{ paddingHorizontal: 4 }}
    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
  >
    <Ionicons name="chevron-back" size={24} color="#2F2A25" />
  </TouchableOpacity>
);

const headerLeftToWelcome = (navigation) => (
  <TouchableOpacity
    onPress={() => navigation.dispatch(StackActions.popToTop())}
    style={{ paddingHorizontal: 4 }}
    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
  >
    <Ionicons name="chevron-back" size={24} color="#2F2A25" />
  </TouchableOpacity>
);

function ClosetStackNavigator() {
  return (
    <ClosetStack.Navigator screenOptions={sharedHeaderOptions}>
      <ClosetStack.Screen
        name="ClosetHome"
        component={ClosetScreen}
        options={{ title: 'My Closet', headerBackVisible: false }}
      />
      <ClosetStack.Screen
        name="SavedShoes"
        component={SavedShoesScreen}
        options={({ navigation }) => ({
          title: 'Saved Shoes',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="OwnedShoes"
        component={OwnedShoesScreen}
        options={({ navigation }) => ({
          title: 'Owned Shoes',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="FootCapture"
        component={FootCaptureScreen}
        options={({ navigation }) => ({
          title: 'Capture Foot Photo',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="Camera"
        component={CameraScreen}
        options={({ navigation }) => ({
          title: 'Camera',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="Measurements"
        component={MeasurementsScreen}
        options={{
          title: 'Your Measurements',
          headerBackVisible: false,
          headerLeft: () => null,
        }}
      />
    </ClosetStack.Navigator>
  );
}

function RecommendationsStackNavigator() {
  return (
    <RecommendationsStack.Navigator screenOptions={sharedHeaderOptions}>
      <RecommendationsStack.Screen
        name="RecommendationsHome"
        component={RecommendationsScreen}
        options={{ title: 'Recommendations' }}
      />
    </RecommendationsStack.Navigator>
  );
}

function ProfileStackNavigator() {
  return (
    <ProfileStack.Navigator screenOptions={sharedHeaderOptions}>
      <ProfileStack.Screen
        name="ProfileHome"
        component={ProfileScreen}
        options={{ title: 'Profile' }}
      />
    </ProfileStack.Navigator>
  );
}

const TAB_BAR_STYLE_VISIBLE = { backgroundColor: '#FFFBF5', borderTopColor: '#E2D4C0' };
const HIDE_TAB_BAR_SCREENS = ['FootCapture', 'Camera', 'Measurements'];

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ navigation }) => {
        const state = navigation.getState();
        const currentTab = state?.routes?.[state.index];
        const stackRoute = currentTab?.name === 'Closet' && currentTab?.state?.routes?.[currentTab.state.index];
        const hideTabBar = stackRoute && HIDE_TAB_BAR_SCREENS.includes(stackRoute.name);
        return {
          headerShown: false,
          tabBarStyle: hideTabBar ? { display: 'none' } : TAB_BAR_STYLE_VISIBLE,
          tabBarActiveTintColor: '#C28A5B',
          tabBarInactiveTintColor: '#6B5F52',
          tabBarLabelStyle: { fontFamily: 'Outfit_600SemiBold', fontSize: 12 },
        };
      }}
    >
      <Tab.Screen
        name="Closet"
        component={ClosetStackNavigator}
        options={{
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="file-tray-full" size={size} color={color} />
          ),
        }}
      />
      <Tab.Screen
        name="Recommendations"
        component={RecommendationsStackNavigator}
        options={{
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="sparkles" size={size} color={color} />
          ),
        }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileStackNavigator}
        options={{
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person" size={size} color={color} />
          ),
        }}
      />
    </Tab.Navigator>
  );
}

export default function App() {
  const [fontsLoaded] = useFonts({
    Outfit_600SemiBold,
    Outfit_400Regular,
  });

  if (!fontsLoaded) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#C28A5B" />
      </View>
    );
  }

  SplashScreen.hideAsync();

  return (
    <SavedShoesProvider>
      <NavigationContainer>
        <StatusBar style="dark" />
        <RootStack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: '#FFF8F0' },
          headerShadowVisible: false,
          headerTitleStyle: { fontFamily: 'Outfit_600SemiBold' },
        }}
      >
        <RootStack.Screen
          name="Welcome"
          component={WelcomeScreen}
          options={{ title: 'Shoe Shopper', headerBackVisible: false }}
        />
        <RootStack.Screen
          name="CreateAccount"
          component={CreateAccountScreen}
          options={({ navigation }) => ({
            title: 'Create Account',
            headerBackVisible: false,
            headerLeft: () => headerLeftToWelcome(navigation),
          })}
        />
        <RootStack.Screen
          name="Login"
          component={LoginScreen}
          options={({ navigation }) => ({
            title: 'Log In',
            headerBackVisible: false,
            headerLeft: () => headerLeftToWelcome(navigation),
          })}
        />
        <RootStack.Screen
          name="MainTabs"
          component={MainTabs}
          options={{ headerShown: false }}
        />
        <RootStack.Screen
          name="FootCapture"
          component={FootCaptureScreen}
          options={({ navigation }) => ({
            title: 'Capture Foot Photo',
            headerLeft: () => headerLeftBack(navigation),
          })}
        />
        <RootStack.Screen
          name="Camera"
          component={CameraScreen}
          options={({ navigation }) => ({
            title: 'Camera',
            headerLeft: () => headerLeftBack(navigation),
          })}
        />
        <RootStack.Screen
          name="Measurements"
          component={MeasurementsScreen}
          options={{
            title: 'Your Measurements',
            headerBackVisible: false,
            headerLeft: () => null,
          }}
        />
        <RootStack.Screen
          name="Recommendations"
          component={RecommendationsScreen}
          options={({ navigation }) => ({
            title: 'Recommendations',
            headerLeft: () => headerLeftBack(navigation),
          })}
        />
        </RootStack.Navigator>
      </NavigationContainer>
    </SavedShoesProvider>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: '#FFF8F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
